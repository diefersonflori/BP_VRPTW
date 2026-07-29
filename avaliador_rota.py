"""Avaliacao centralizada de rotas (Solomon e Petrobras).

Concentra regras hoje duplicadas em varias funcoes locais de metodos.py e
parcialmente em solucao.py: custo/tempo de viagem, estrutura da rota,
ordem de escalas por plataforma, capacidade dinamica de deck/diesel/agua
(Petrobras) e a propagacao de cronograma respeitando TODAS as janelas de
tempo de cada no (nao so a primeira).

A classe e sem estado (todo o estado vem de `inst`/`k`/`seq` em cada
chamada), por isso pode ser instanciada uma unica vez e reutilizada -- ver
`AVALIADOR_ROTA_PADRAO` no fim do arquivo.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResultadoRota:
    viavel: bool
    motivo: str
    custo: Optional[float]
    tempo_final: Optional[float]
    cronograma: list = field(default_factory=list)
    carga_deck_maxima: Optional[float] = None


class AvaliadorRota:
    """Regras e metricas de uma rota (sem estado). Ver docstring do modulo."""

    EPS = 1e-6

    # ------------------------------------------------------------------
    # Blocos basicos (compartilhados por Solomon e Petrobras)
    # ------------------------------------------------------------------
    def clientes_da_rota(self, inst, seq):
        """Nos de cliente (1..nbcd) presentes na sequencia, na ordem em que aparecem."""
        return [no for no in seq if 1 <= no <= inst.nbcd]

    def tempo_servico(self, inst, no):
        """Tempo de servico (primeira/unica entrada de SERVICE_TIME), em segundos."""
        noh = inst.noh[no]
        return float(noh.SERVICE_TIME[0]) if noh.SERVICE_TIME else 0.0

    def tempo_viagem(self, inst, k, i, j):
        """Tempo de viagem do arco i->j para o veiculo k, em segundos (inclui setups, ja embutidos em matriz_distancia)."""
        return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

    def custo_rota(self, inst, k, seq):
        """Custo de uma rota = soma dos tempos de viagem dos arcos (sem espera/servico)."""
        return sum(self.tempo_viagem(inst, k, seq[t], seq[t + 1]) for t in range(len(seq) - 1))

    def validar_estrutura_rota(self, inst, seq):
        """Regra 1+2: comeca no deposito 0, termina em nbn-1, sem pedido repetido.
        Retorna (bool, motivo)."""
        depf = inst.nbn - 1
        if not seq or seq[0] != 0 or seq[-1] != depf:
            return False, "rota_sem_depositos"

        vistos = set()
        for no in self.clientes_da_rota(inst, seq):
            if no in vistos:
                return False, f"pedido_repetido_{no}"
            vistos.add(no)

        return True, ""

    # ------------------------------------------------------------------
    # Regras especificas Petrobras
    # ------------------------------------------------------------------
    def plataforma_petro(self, inst, no):
        """Identificador de plataforma do pedido `no` (mesma regra usada em
        _montar_dados_petro_cpp e no validador do modelo exato)."""
        if not (1 <= no <= inst.nbcd):
            return None

        dp = inst.dados_petro
        nome = str(dp["nomes"][no])
        if "_order" in nome:
            return nome.split("_order", 1)[0]

        # Fallback para instancias sem nome padronizado.
        lat = round(float(dp["lat"][no]), 6)
        lon = round(float(dp["lon"][no]), 6)
        return lat, lon

    def validar_ordem_plataformas_petro(self, inst, seq):
        """Regra 3+4+5: uma plataforma nao pode ser revisitada apos encerrada
        (nao-consecutiva) e, dentro de uma escala, coleta de backload sempre
        antes de qualquer entrega. Retorna (bool, motivo).

        Mesma logica (via `plataformas_encerradas`) usada em
        Solucao.ordem_plataformas_petro_valida, no validador independente de
        metodo_exato_petro e em petro_ordem_plataformas_valida (PD_PARA_PYTHON.cpp)."""
        dp = inst.dados_petro
        eps = self.EPS

        plataforma_atual = None
        plataformas_encerradas = set()
        entrega_iniciada = False

        for no in seq:
            if not (1 <= no <= inst.nbcd):
                continue

            plataforma = self.plataforma_petro(inst, no)

            if plataforma != plataforma_atual:
                if plataforma_atual is not None:
                    plataformas_encerradas.add(plataforma_atual)
                if plataforma in plataformas_encerradas:
                    return False, f"retorno_plataforma_{plataforma}"
                plataforma_atual = plataforma
                entrega_iniciada = False

            tem_coleta = float(dp["dem_deck_backload"][no]) > eps
            tem_entrega = (
                float(dp["dem_deck_load"][no]) > eps
                or float(dp["dem_diesel"][no]) > eps
                or float(dp["dem_agua"][no]) > eps
            )

            if tem_coleta and entrega_iniciada:
                return False, f"coleta_apos_entrega_no_{no}"
            if tem_entrega:
                entrega_iniciada = True

        return True, ""

    def validar_cargas_petro(self, inst, k, seq):
        """Regra 8+9+10+11: navio sai da base com todas as entregas da viagem;
        deck atualizado dinamicamente por escala (backload primeiro, entrega
        depois); diesel/agua respeitam capacidade fixa do tanque.
        Retorna (bool, motivo, carga_deck_maxima).

        Mesma logica de Solucao.viavel_cargas_petro, com o pico de deck
        (carga_deck_maxima) reportado como observacao adicional."""
        dp = getattr(inst, "dados_petro", None)
        if dp is None:
            return True, "", None

        ordem_ok, motivo = self.validar_ordem_plataformas_petro(inst, seq)
        if not ordem_ok:
            return False, motivo, None

        veic = inst.veiculos[k]
        cap_deck = float(getattr(veic, "cap_deck", veic.capacidade))
        cap_diesel = float(getattr(veic, "cap_diesel", float("inf")))
        cap_agua = float(getattr(veic, "cap_agua", float("inf")))
        eps = self.EPS

        clientes = self.clientes_da_rota(inst, seq)

        # O navio sai da base levando todas as entregas de convés/diesel/agua da viagem.
        deck = sum(float(dp["dem_deck_load"][no]) for no in clientes)
        diesel = sum(float(dp["dem_diesel"][no]) for no in clientes)
        agua = sum(float(dp["dem_agua"][no]) for no in clientes)

        if deck > cap_deck + eps:
            return False, "capacidade_deck_inicial", deck
        if diesel > cap_diesel + eps:
            return False, "capacidade_diesel", deck
        if agua > cap_agua + eps:
            return False, "capacidade_agua", deck

        pico_deck = deck
        pos = 0
        while pos < len(clientes):
            plataforma = self.plataforma_petro(inst, clientes[pos])
            fim = pos
            coleta_plataforma = 0.0
            entrega_plataforma = 0.0

            # Pedidos consecutivos pertencentes a mesma escala.
            while fim < len(clientes) and self.plataforma_petro(inst, clientes[fim]) == plataforma:
                no = clientes[fim]
                coleta_plataforma += float(dp["dem_deck_backload"][no])
                entrega_plataforma += float(dp["dem_deck_load"][no])
                fim += 1

            # Regra operacional: primeiro embarca os backloads da escala.
            deck += coleta_plataforma
            pico_deck = max(pico_deck, deck)
            if deck > cap_deck + eps:
                return False, "capacidade_deck_dinamica", pico_deck

            # Depois descarrega as entregas da escala.
            deck -= entrega_plataforma
            if deck < -eps:
                return False, "deck_negativo", pico_deck

            pos = fim

        return True, "", pico_deck

    def _janelas_no(self, inst, no):
        """Janelas (ready, due, service) do no, ordenadas por inicio (regra 6).
        Mesmo criterio de SUB_HEUR_ALLBESTINSERTION.verifica_viabilidade e do
        bloco PETRO em PD_PARA_PYTHON.cpp (aw/bw por no)."""
        noh = inst.noh[no]
        if noh.READY_TIME and noh.DUE_DATE:
            servicos = noh.SERVICE_TIME if noh.SERVICE_TIME else [0.0] * len(noh.READY_TIME)
            janelas = [
                (
                    float(noh.READY_TIME[r]),
                    float(noh.DUE_DATE[r]),
                    float(servicos[r]) if r < len(servicos) else float(servicos[0]),
                )
                for r in range(len(noh.READY_TIME))
            ]
        else:
            janelas = [(0.0, float("inf"), 0.0)]
        return sorted(janelas, key=lambda w: w[0])

    def calcular_cronograma(self, inst, k, seq):
        """Regra 6+7: propaga o cronograma testando, em cada no, todas as
        janelas de tempo (nao so READY_TIME[0]/DUE_DATE[0]) e escolhendo a
        primeira que acomoda o servico; considera readiness do navio no
        deposito inicial. Retorna ResultadoRota (sem custo/carga_deck_maxima,
        preenchidos por avaliar_rota_petro)."""
        estrutura_ok, motivo = self.validar_estrutura_rota(inst, seq)
        if not estrutura_ok:
            return ResultadoRota(False, motivo, None, None, [])

        dep0 = seq[0]
        veic = inst.veiculos[k]
        eps = self.EPS

        a0, b0, s0 = self._janelas_no(inst, dep0)[0]
        tempo = max(a0, float(getattr(veic, "readiness", a0)))
        if tempo > b0 + eps:
            return ResultadoRota(False, "deposito_fora_da_janela", None, None, [])
        tempo += s0

        cronograma = [{
            "no": dep0, "chegada": tempo - s0, "inicio_servico": tempo - s0,
            "fim_servico": tempo, "janela": 0,
        }]

        for pos in range(1, len(seq)):
            i, j = seq[pos - 1], seq[pos]
            chegada = tempo + self.tempo_viagem(inst, k, i, j)

            achou = False
            for idx_janela, (aj, bj, sj) in enumerate(self._janelas_no(inst, j)):
                inicio = max(chegada, aj)
                fim = inicio + sj
                if fim <= bj + eps:
                    cronograma.append({
                        "no": j, "chegada": chegada, "inicio_servico": inicio,
                        "fim_servico": fim, "janela": idx_janela,
                    })
                    tempo = fim
                    achou = True
                    break

            if not achou:
                return ResultadoRota(False, f"sem_janela_viavel_no_{j}", None, None, cronograma)

        return ResultadoRota(True, "", None, tempo, cronograma)

    def avaliar_rota_petro(self, inst, k, seq):
        """Avaliacao completa Petrobras: estrutura + ordem de plataformas +
        cargas dinamicas (deck/diesel/agua) + cronograma multi-janela."""
        estrutura_ok, motivo = self.validar_estrutura_rota(inst, seq)
        if not estrutura_ok:
            return ResultadoRota(False, motivo, None, None, [], None)

        cargas_ok, motivo, carga_deck_maxima = self.validar_cargas_petro(inst, k, seq)
        if not cargas_ok:
            return ResultadoRota(False, motivo, None, None, [], carga_deck_maxima)

        cronograma_resultado = self.calcular_cronograma(inst, k, seq)
        if not cronograma_resultado.viavel:
            return ResultadoRota(
                False, cronograma_resultado.motivo, None, None,
                cronograma_resultado.cronograma, carga_deck_maxima,
            )

        custo = self.custo_rota(inst, k, seq)
        return ResultadoRota(
            True, "", custo, cronograma_resultado.tempo_final,
            cronograma_resultado.cronograma, carga_deck_maxima,
        )

    # ------------------------------------------------------------------
    # Solomon (sem regras Petrobras: janela unica, carga acumulada por demanda)
    # ------------------------------------------------------------------
    def _ready0(self, inst, no):
        return float(inst.noh[no].READY_TIME[0]) if inst.noh[no].READY_TIME else 0.0

    def _due0(self, inst, no):
        return float(inst.noh[no].DUE_DATE[0]) if inst.noh[no].DUE_DATE else 1e9

    def _demand0(self, inst, no):
        return float(getattr(inst.noh[no], "DEMAND", 0.0))

    def avaliar_rota_solomon(self, inst, k, seq):
        """Avaliacao classica Solomon: janela tradicional (so o indice 0),
        carga acumulada por demanda e capacidade Q do veiculo. Preserva
        exatamente o comportamento historico das construtivas para
        instancias sem `dados_petro`."""
        estrutura_ok, motivo = self.validar_estrutura_rota(inst, seq)
        if not estrutura_ok:
            return ResultadoRota(False, motivo, None, None, [], None)

        Q = inst.veiculos[k].capacidade
        carga = 0.0
        tempo = 0.0
        cronograma = []

        for t in range(1, len(seq)):
            i, j = seq[t - 1], seq[t]
            tempo = max(self._ready0(inst, j), tempo + self.tempo_servico(inst, i) + self.tempo_viagem(inst, k, i, j))
            if tempo + self.tempo_servico(inst, j) > self._due0(inst, j):
                return ResultadoRota(False, f"janela_violada_no_{j}", None, None, cronograma, carga)

            if 1 <= j <= inst.nbcd:
                carga += self._demand0(inst, j)
            if carga > Q:
                return ResultadoRota(False, "capacidade_excedida", None, None, cronograma, carga)

            cronograma.append({"no": j, "chegada": tempo, "carga": carga})

        custo = self.custo_rota(inst, k, seq)
        return ResultadoRota(True, "", custo, tempo, cronograma, carga)

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------
    def avaliar_rota(self, inst, k, seq):
        """Avalia com as regras Petrobras se `inst.dados_petro` existir;
        caso contrario, usa a avaliacao Solomon classica."""
        if hasattr(inst, "dados_petro"):
            return self.avaliar_rota_petro(inst, k, seq)
        return self.avaliar_rota_solomon(inst, k, seq)


# Instancia compartilhada: a classe nao tem estado, entao um unico objeto
# pode ser reutilizado por Metodos e Solucao sem recria-lo a cada chamada.
AVALIADOR_ROTA_PADRAO = AvaliadorRota()
