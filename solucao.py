import json
from pprint import pprint
import os
import re
import csv
import instancia
from pathlib import Path
#import matplotlib.pyplot as plt
import json

from avaliador_rota import AVALIADOR_ROTA_PADRAO


class Solucao:
    # tipo -> {"html": arquivo padrao, "js": arquivo gerado, "rotulo": nome amigavel}
    CONFIG_PLOTJS = {
        "construtiva": {"html": "gantt_petro_construtiva.html", "js": "petroConstr.js", "rotulo": "Solução construtiva"},
        "bp": {"html": "gantt_petroBp.html", "js": "petroBP.js", "rotulo": "Branch-and-Price"},
        "exato": {"html": "gantt_petro_exato.html", "js": "petroEx.js", "rotulo": "Modelo exato"},
    }

    def __init__(self, nbv, nbn):
        # bin_visitas[k][i][j]
        #self.bin_visitas = [[[0 for _ in range(nbn)] for _ in range(nbn)] for _ in range(nbv)]
        #self.bin_visitas = []
        #self.custo = 0
        #self.lista_de_visitas = []    # list[n_bv][n_rotas][n_clientes]
        self.sequencias_solucoes = [] # list[n_bv][n_rotas][seq]
        #self.cost = []                # list[n_bv][n_rotas][custo]
        self.lambdac = []             # list[n_bv][n_rotas][lambdac]
        #self.numero_de_rotas = []     # list[n_bv]
        self.rotas = {} #aqui ficara toda a solucao
        self.custo = -1
        self.best_obj = -1
        self.custo = -1
        #GC
        self.rotas_escolhidas = {}

        # formato canonico: {"construtiva"|"bp"|"exato": {k: {"sequencias": [...], "custos": [...]}}}
        self.solucoes = {}

        # cronogramas Silva (objective_mode=="silva2024") para o PlotJS: {"construtiva"|
        # "bp"|"exato": {k: {"AT","B","P","R","F","hB_saida","hB_retorno","cronologia",...}}}.
        # Cada entrada por navio e o dict retornado por Metodos.avaliar_rota_silva2024()
        # (construtiva/bp) ou sol.exato_petro_silva_diag[k] (exato) -- ver
        # registrar_cronograma_plotjs. Estrutura ISOLADA de self.solucoes (nao mistura
        # com o formato canonico usado pelo modo petrobras).
        self.cronogramas_plotjs = {}

        self.construtivas = [0, 0, 0, 0, 0]
        self.TIME_MAX = 3600


        #para gerar o grafico -exportar convergencia
        self.log_convergencia = []
        self.melhor_ub = float("inf")
        self.iter_gc = 5
        self.nb_iteracoes=0
        #para gerar o grafico -exportar convergencia


        self.motivoConv="GERAL"

        ##IniEstabilizacao Dual
        #centro das duais
        self.pi_bar= None
        #LARgura da caixa
        self.gamma_pi = 100.0
        #largura da caixa
        self.alpha_estab= 0.1
        #historico
        self.historico_pi=[]
        ##FimEstabilizacao Dual
        self.SemMelhora=[]#sem melhora em cada nó



        ##################alteracao- salvar lp nao so o mip

        ######################################################################################################&&
        self.FO_TARGET = 362.4

        # =========================
        # Melhores valores globais
        # =========================

        self.melhor_lp_com_slack = float("inf")
        self.iter_melhor_lp_com_slack = ""
        self.no_melhor_lp_com_slack = ""

        self.melhor_lp_valido = float("inf")
        self.iter_melhor_lp_valido = ""
        self.no_melhor_lp_valido = ""

        self.melhor_inteiro = float("inf")
        self.iter_melhor_inteiro = ""
        self.no_melhor_inteiro = ""

        # =========================
        # Targets
        # =========================

        self.achou_lp_target = False
        self.iter_lp_target = ""
        self.tempo_lp_target = ""
        self.no_lp_target = ""

        self.achou_int_target = False
        self.iter_int_target = ""
        self.tempo_int_target = ""
        self.no_int_target = ""
        ######################################################################################################&&

    time_initial = 0
    FO_TARGET = -1
    TIME_TARGET = 99999999

    def registrar_solucao(self, nome, rotas):
        """Normaliza `rotas` para o formato canonico {k: {"sequencias": [...], "custos": [...]}}
        e grava em self.solucoes[nome]. Aceita como entrada: dict k->{"sequencias":[...], ...},
        dict k->sequencia unica, ou dict k->lista de sequencias. Sequencias copiadas com list()."""
        canonico = {}
        for k, ent in rotas.items():
            if isinstance(ent, dict):
                seqs = [list(s) for s in ent.get("sequencias", [])]
                custos = list(ent.get("custos", []))
            elif ent and isinstance(ent[0], (list, tuple)):
                seqs = [list(s) for s in ent]
                custos = []
            else:
                seqs = [list(ent)] if ent else []
                custos = []
            canonico[k] = {"sequencias": seqs, "custos": custos}
        self.solucoes[nome] = canonico

    def registrar_cronograma_plotjs(self, nome_solucao, cronogramas):
        """Registra, para uso exclusivo do PlotJS em modo silva2024, o cronograma por
        navio de `nome_solucao` ("construtiva"|"bp"|"exato"). `cronogramas` e um dict
        {k: dict-resultado}, onde dict-resultado e o retorno de
        Metodos.avaliar_rota_silva2024() (construtiva/bp) ou uma entrada de
        sol.exato_petro_silva_diag (exato) -- ambos ja trazem AT/B/P/R/F/hB_saida/
        hB_retorno/cronologia em HORAS. Nao recalcula nada; so armazena."""
        self.cronogramas_plotjs[nome_solucao] = cronogramas

    def exportar_visualizacao(self, inst, nome_solucao, caminho_js):
        """Exporta self.solucoes[nome_solucao] (formato canonico) para caminho_js
        (window.DADOS = {...}), consumido pelos gantt_petro*.html. Tempos em HORAS.
        Mesma propagacao de relatorio_cronograma_petro (mais cedo possivel, servico
        comeca na janela)."""
        dados = self._montar_dados_visualizacao(inst, nome_solucao)
        if dados is None:
            return None
        self._exportar_js_plotjs(dados, caminho_js)
        print(f"[GANTT] dados exportados em {caminho_js}")
        return dados

    def _montar_dados_visualizacao(self, inst, nome_solucao):
        """Monta o dict de dados (mesmo formato de window.DADOS) para self.solucoes[nome_solucao],
        sem escrever arquivo. Retorna None se a solucao nao estiver registrada ou faltar dados_petro."""
        if getattr(inst, "objective_mode", "petrobras") == "silva2024":
            # Modo Silva: a reconstrucao generica abaixo (matriz_distancia[i][j]/velocidade)
            # NAO reflete a fisica silva2024 (navegacao piecewise VL/VH, SP/SET por entrada
            # de plataforma, B resolvido pelo Gurobi != AT). Ramo petrobras (abaixo, resto
            # deste metodo) permanece INTACTO e byte-a-byte igual.
            return self._montar_dados_visualizacao_silva2024(inst, nome_solucao)

        if nome_solucao not in self.solucoes:
            print(f"[GANTT] solucao '{nome_solucao}' nao registrada "
                  f"(chame registrar_solucao antes de exportar_visualizacao)")
            return None
        rotas_escolhidas = self.solucoes[nome_solucao]
        if not hasattr(inst, "dados_petro"):
            return None
        H = 3600.0
        dp = inst.dados_petro
        nomes = dp["nomes"]
        depf = inst.nbn - 1

        def plataforma(nome):
            return "BASE" if nome.startswith("BASE") else nome.split("_order")[0]

        nos_js = []
        for i in range(inst.nbcd + 1):
            nos_js.append({
                "id": i, "nome": nomes[i], "plataforma": plataforma(nomes[i]),
                "lat": dp["lat"][i], "lon": dp["lon"][i],
                "janelas": [[a / H, b / H] for a, b in
                            zip(inst.noh[i].READY_TIME, inst.noh[i].DUE_DATE)],
                "servico_h": (inst.noh[i].SERVICE_TIME[0] / H) if inst.noh[i].SERVICE_TIME else 0.0,
                "deck": float(dp["dem_deck_load"][i] + dp["dem_deck_backload"][i]),
                "deck_load": float(dp["dem_deck_load"][i]),
                "deck_backload": float(dp["dem_deck_backload"][i]),
                "diesel": float(dp["dem_diesel"][i]),
                "agua": float(dp["dem_agua"][i]),
            })

        navios_js = []
        fo_total = 0.0
        for k in range(inst.nbv):
            ent = rotas_escolhidas.get(
                k,
                {
                    "sequencias": [],
                    "custos": []
                }
            )
            seqs = list(ent.get("sequencias", []))
            veic = inst.veiculos[k]
            seq = list(seqs[0]) if seqs else [0, depf]

            nav = {"k": k, "nome": getattr(veic, "nome", ""), "ocioso": len(seq) <= 2,
                   "segmentos": [], "visitas": [],
                   "navegacao_h": 0.0, "servico_h": 0.0, "espera_h": 0.0,
                   "capacidades": {
                    "deck": float(getattr(veic, "cap_deck", getattr(veic, "capacidade", dp.get("capacidade", 0.0)))),
                    "diesel": float(getattr(veic, "cap_diesel", dp.get("cap_diesel", 0.0))),
                    "agua": float(getattr(veic, "cap_agua", dp.get("cap_agua", 0.0))),
                    },"retorno_h": 0.0}
            if nav["ocioso"]:
                navios_js.append(nav)
                continue

            tempo = float(inst.noh[0].READY_TIME[0])
            for a in range(len(seq) - 1):
                i, j = seq[a], seq[a + 1]
                arco = inst.matriz_distancia[i][j] / veic.velocidade
                partida_i = tempo + (inst.noh[i].SERVICE_TIME[0] if a > 0 else 0.0)
                chegada = partida_i + arco
                nav["segmentos"].append({"tipo": "nav", "ini": partida_i / H, "fim": chegada / H})
                nav["navegacao_h"] += arco / H
                if j == depf:
                    nav["retorno_h"] = chegada / H
                    tempo = chegada
                    continue
                no_j = inst.noh[j]
                ini, jidx, janela = None, None, None
                servico_j = no_j.SERVICE_TIME[0] if no_j.SERVICE_TIME else 0.0
                for r in range(len(no_j.DUE_DATE)):
                    ini_cand = max(chegada, float(no_j.READY_TIME[r]))
                    if ini_cand + servico_j <= no_j.DUE_DATE[r] + 1e-6:
                        ini = ini_cand
                        jidx, janela = r, [no_j.READY_TIME[r] / H, no_j.DUE_DATE[r] / H]
                        break
                if ini is None:
                    ini, jidx, janela = chegada, -1, None
                fim = ini + (no_j.SERVICE_TIME[0] if no_j.SERVICE_TIME else 0.0)
                if ini > chegada + 1e-6:
                    nav["segmentos"].append({"tipo": "espera", "ini": chegada / H, "fim": ini / H})
                    nav["espera_h"] += (ini - chegada) / H
                nav["segmentos"].append({"tipo": "servico", "ini": ini / H, "fim": fim / H,
                                         "plataforma": plataforma(nomes[j])})
                nav["servico_h"] += (fim - ini) / H
                nav["visitas"].append({
                    "no": j, "nome": nomes[j], "plataforma": plataforma(nomes[j]),
                    "chegada": chegada / H, "ini": ini / H, "fim": fim / H,
                    "espera": (ini - chegada) / H, "janela": janela, "jidx": jidx,
                    "janelas": [[x / H, y / H] for x, y in
                                zip(no_j.READY_TIME, no_j.DUE_DATE)],
                })
                tempo = ini
            fo_total += nav["navegacao_h"] * H
            navios_js.append(nav)

        dados = {"instancia": getattr(inst, "fileName", ""),
                 "horizonte_h": inst.noh[0].DUE_DATE[0] / H if inst.noh[0].DUE_DATE else 168.0,
                 "fo_total_s": fo_total, "nos": nos_js, "navios": navios_js}
        return dados

    def _montar_dados_visualizacao_silva2024(self, inst, nome_solucao):
        """Equivalente a _montar_dados_visualizacao, exclusivo de objective_mode=="silva2024".
        NAO duplica a formula fisica Silva (navegacao piecewise VL/VH, SP/SET, B resolvido
        pelo Gurobi): usa exclusivamente os cronogramas ja calculados por
        Metodos.avaliar_rota_silva2024()/metodo_exato_petro e registrados via
        registrar_cronograma_plotjs (self.cronogramas_plotjs[nome_solucao][k]). Se o
        cronograma de um navio nao foi registrado, o navio e mostrado como ocioso (sem
        inventar horario). Retorna None nas mesmas condicoes de _montar_dados_visualizacao
        (solucao nao registrada / sem dados_petro)."""
        if nome_solucao not in self.solucoes:
            print(f"[GANTT-SILVA] solucao '{nome_solucao}' nao registrada "
                  f"(chame registrar_solucao antes de exportar_visualizacao)")
            return None
        rotas_escolhidas = self.solucoes[nome_solucao]
        if not hasattr(inst, "dados_petro"):
            return None

        H = 3600.0
        dp = inst.dados_petro
        nomes = dp["nomes"]
        depf = inst.nbn - 1
        cronogramas = self.cronogramas_plotjs.get(nome_solucao, {})

        def plataforma(nome):
            return "BASE" if nome.startswith("BASE") else nome.split("_order")[0]

        # nos_js: MESMA logica (dado bruto, sem formula fisica) de
        # _montar_dados_visualizacao -- duplicada aqui de proposito, para manter aquele
        # metodo intacto para petrobras (ver pedido: "preservar esse codigo INTACTO").
        nos_js = []
        for i in range(inst.nbcd + 1):
            nos_js.append({
                "id": i, "nome": nomes[i], "plataforma": plataforma(nomes[i]),
                "lat": dp["lat"][i], "lon": dp["lon"][i],
                "janelas": [[a / H, b / H] for a, b in
                            zip(inst.noh[i].READY_TIME, inst.noh[i].DUE_DATE)],
                "servico_h": (inst.noh[i].SERVICE_TIME[0] / H) if inst.noh[i].SERVICE_TIME else 0.0,
                "deck": float(dp["dem_deck_load"][i] + dp["dem_deck_backload"][i]),
                "deck_load": float(dp["dem_deck_load"][i]),
                "deck_backload": float(dp["dem_deck_backload"][i]),
                "diesel": float(dp["dem_diesel"][i]),
                "agua": float(dp["dem_agua"][i]),
            })

        navios_js = []
        navegacao_total_h = 0.0
        for k in range(inst.nbv):
            ent = rotas_escolhidas.get(k, {"sequencias": [], "custos": []})
            seqs = list(ent.get("sequencias", []))
            veic = inst.veiculos[k]
            seq = list(seqs[0]) if seqs else [0, depf]

            cronog_k = cronogramas.get(k)
            nav = {"k": k, "nome": getattr(veic, "nome", ""),
                   "ocioso": len(seq) <= 2 or cronog_k is None,
                   "segmentos": [], "visitas": [],
                   "navegacao_h": 0.0, "servico_h": 0.0, "espera_h": 0.0,
                   "capacidades": {
                       "deck": float(getattr(veic, "cap_deck", getattr(veic, "capacidade", dp.get("capacidade", 0.0)))),
                       "diesel": float(getattr(veic, "cap_diesel", dp.get("cap_diesel", 0.0))),
                       "agua": float(getattr(veic, "cap_agua", dp.get("cap_agua", 0.0))),
                   }, "retorno_h": 0.0}
            if nav["ocioso"]:
                navios_js.append(nav)
                continue

            AT = float(cronog_k.get("AT", 0.0))
            B = float(cronog_k.get("B", AT))
            P = float(cronog_k.get("P", B))
            R = float(cronog_k.get("R", P))
            F = float(cronog_k.get("F", R))
            hB_saida = float(cronog_k.get("hB_saida", P - B))
            hB_retorno = float(cronog_k.get("hB_retorno", F - R))

            # AT -> B: espera/disponibilidade pre-berco, se houver.
            if B > AT + 1e-9:
                nav["segmentos"].append({"tipo": "espera", "ini": AT, "fim": B})
                nav["espera_h"] += (B - AT)

            # B -> P: carregamento na base (deck+diesel+agua).
            nav["segmentos"].append({"tipo": "base_loading", "ini": B, "fim": P, "plataforma": "BASE"})

            cronologia = cronog_k.get("cronologia", [])
            tempo_fim_anterior = P
            for evento in cronologia:
                if evento.get("evento") == "retorno_base":
                    chegada_h = float(evento["chegada_h"])
                    if chegada_h > tempo_fim_anterior + 1e-9:
                        nav["segmentos"].append({"tipo": "nav", "ini": tempo_fim_anterior, "fim": chegada_h})
                        nav["navegacao_h"] += chegada_h - tempo_fim_anterior
                    tempo_fim_anterior = chegada_h
                    continue

                no = evento["no"]
                chegada_h = float(evento["chegada_h"])
                inicio_h = float(evento["inicio_h"])
                fim_h = float(evento["fim_h"])
                espera_h = float(evento.get("espera_h", 0.0))
                janela_idx = evento.get("janela_idx")

                if chegada_h > tempo_fim_anterior + 1e-9:
                    nav["segmentos"].append({"tipo": "nav", "ini": tempo_fim_anterior, "fim": chegada_h})
                    nav["navegacao_h"] += chegada_h - tempo_fim_anterior

                if espera_h > 1e-6:
                    nav["segmentos"].append({"tipo": "espera", "ini": chegada_h, "fim": inicio_h})
                    nav["espera_h"] += espera_h

                nav["segmentos"].append({"tipo": "servico", "ini": inicio_h, "fim": fim_h,
                                         "plataforma": plataforma(nomes[no])})
                nav["servico_h"] += fim_h - inicio_h

                janelas_no = nos_js[no]["janelas"] if no < len(nos_js) else []
                janela = janelas_no[janela_idx] if janela_idx is not None and janela_idx < len(janelas_no) else None
                nav["visitas"].append({
                    "no": no, "nome": nomes[no], "plataforma": plataforma(nomes[no]),
                    "chegada": chegada_h, "ini": inicio_h, "fim": fim_h,
                    "espera": espera_h, "janela": janela, "jidx": janela_idx,
                    "janelas": janelas_no,
                })
                tempo_fim_anterior = fim_h

            # R -> F: descarga de backload na base.
            nav["retorno_h"] = R
            if F > R + 1e-9:
                nav["segmentos"].append({"tipo": "base_unloading", "ini": R, "fim": F, "plataforma": "BASE"})

            navegacao_total_h += nav["navegacao_h"]
            navios_js.append(nav)

        # fo_total_s: MESMO campo/unidade (segundos) que o ramo petrobras ja preenche
        # (total de navegacao, so informativo no cabecalho do HTML -- D.fo_total_s).
        # NAO e a FO Silva (essa vem de self.solucoes[tipo]["custos"] via
        # _obter_fo_solucao/comparativo, preenchido por exportar_plotjs, nunca
        # recalculado aqui -- ver pedido: "Não usar navegacao_h*3600 como FO").
        dados = {"instancia": getattr(inst, "fileName", ""),
                 "horizonte_h": inst.noh[0].DUE_DATE[0] / H if inst.noh[0].DUE_DATE else 168.0,
                 "fo_total_s": navegacao_total_h * H, "nos": nos_js, "navios": navios_js}
        return dados

    def _exportar_js_plotjs(self, dados, caminho_js):
        """Escreve `window.DADOS = {...}` (ou `null`, se dados is None) em caminho_js."""
        with open(caminho_js, "w", encoding="utf-8") as f:
            f.write("window.DADOS = ")
            if dados is None:
                f.write("null")
            else:
                json.dump(dados, f, ensure_ascii=False, indent=1)
            f.write(";\n")

    def _resolver_pasta_base_plotjs(self):
        """Localiza PlotJS/basePadrao a partir da localizacao real deste arquivo,
        independente do diretorio de trabalho atual (a bateria roda em pastas work/ paralelas)."""
        pasta = Path(__file__).resolve().parent / "PlotJS" / "basePadrao"
        if not pasta.is_dir():
            raise FileNotFoundError(f"Pasta PlotJS/basePadrao nao encontrada: {pasta}")
        return pasta

    def _ajustar_script_html(self, texto, nome_js):
        padrao_script = re.compile(r'script\.src\s*=\s*["\'][^"\']+["\']\s*\+\s*Date\.now\(\)\s*;')
        texto, quantidade = padrao_script.subn(f'script.src = "{nome_js}?v=" + Date.now();', texto, count=1)
        if quantidade != 1:
            raise RuntimeError(f"Nao foi encontrada exatamente uma linha script.src dinamica no HTML de {nome_js}")

        nomes_antigos = ["visualizacao_dados.js", "visualizacao_dadosBP.js", "visualizacao_dados_construtiva.js", "visualizacao_dados_exato.js", "petroConstr.js", "petroBP.js", "PetroBp.js", "petroEx.js"]
        for nome_antigo in nomes_antigos:
            texto = texto.replace(nome_antigo, nome_js)
        return texto

    def _copiar_html_plotjs(self, html_origem, html_destino, nome_js):
        """Copia html_origem para html_destino apontando o script carregado para nome_js.
        Nao altera o HTML padrao (a substituicao e feita somente na copia)."""
        texto = Path(html_origem).read_text(encoding="utf-8")
        texto = self._ajustar_script_html(texto, nome_js)
        Path(html_destino).write_text(texto, encoding="utf-8")

    def _nome_limpo_instancia(self, inst):
        bruto = Path(getattr(inst, "fileName", "") or "").stem
        return re.sub(r"[^A-Za-z0-9._-]+", "_", bruto).strip("_")

    def _obter_fo_solucao(self, tipo):
        """Obtem a FO somando os custos das rotas ja registradas em self.solucoes[tipo]
        (unica fonte de verdade). Retorna None quando a abordagem nao foi registrada."""
        rotas = self.solucoes.get(tipo)
        if not rotas:
            return None

        custos = [float(custo) for entrada in rotas.values() for custo in entrada.get("custos", [])]
        return sum(custos) if custos else None

    def _montar_resumo_comparativo_plotjs(self, inst, fos, tempos):
        return {
            "instancia_nome": self._nome_limpo_instancia(inst),
            "fo_construtiva": fos.get("construtiva"),
            "fo_bp": fos.get("bp"),
            "fo_exato": fos.get("exato"),
            "tempo_construtiva": tempos.get("construtiva"),
            "tempo_bp": tempos.get("bp"),
            "tempo_exato": tempos.get("exato"),
        }

    def exportar_plotjs(self, inst, pasta_saida, tempo_construtiva=None, tempo_bp=None, tempo_exato=None):
        """Orquestra a exportacao completa do pacote PlotJS (HTMLs padrao + JS) para as tres
        abordagens (construtiva, bp, exato), usando as solucoes ja registradas em
        self.solucoes via registrar_solucao. Qualquer abordagem ou tempo ausente e
        exportado como null, sem impedir a exportacao das demais."""
        pasta_saida = Path(pasta_saida)
        pasta_saida.mkdir(parents=True, exist_ok=True)
        pasta_base = self._resolver_pasta_base_plotjs()

        tempos = {"construtiva": tempo_construtiva, "bp": tempo_bp, "exato": tempo_exato}
        fos = {tipo: self._obter_fo_solucao(tipo) for tipo in self.CONFIG_PLOTJS}
        comparativo = self._montar_resumo_comparativo_plotjs(inst, fos, tempos)

        for tipo, config in self.CONFIG_PLOTJS.items():
            caminho_js = pasta_saida / config["js"]
            self._copiar_html_plotjs(pasta_base / config["html"], pasta_saida / config["html"], config["js"])

            dados = self._montar_dados_visualizacao(inst, tipo)
            if dados is not None:
                dados["solucao_atual"] = tipo
                dados["comparativo"] = comparativo
            self._exportar_js_plotjs(dados, caminho_js)

            status = "ok" if dados is not None else "sem solucao (DADOS=null)"
            print(f"[PLOTJS] {config['rotulo']} ({tipo}): {status} -> {caminho_js.name}")

        print(f"[PLOTJS] pacote exportado em {pasta_saida}")
        return pasta_saida

    def plataforma_petro(self, inst, no):
        """Delegado a AvaliadorRota.plataforma_petro (fonte unica desta regra)."""
        return AVALIADOR_ROTA_PADRAO.plataforma_petro(inst, no)

    def ordem_plataformas_petro_valida(self, inst, seq):
        """Delegado a AvaliadorRota (silva2024 usa a precedencia por
        compartimento de validar_ordem_plataformas_silva2024; petrobras
        mantem validar_ordem_plataformas_petro, inalterado)."""
        modo_silva = getattr(inst, "objective_mode", "petrobras") == "silva2024"
        if modo_silva:
            viavel, _motivo = AVALIADOR_ROTA_PADRAO.validar_ordem_plataformas_silva2024(inst, seq)
        else:
            viavel, _motivo = AVALIADOR_ROTA_PADRAO.validar_ordem_plataformas_petro(inst, seq)
        return viavel

    def viavel_cargas_petro(self, inst, k, seq):
        """Delegado a AvaliadorRota.validar_cargas_petro (fonte unica desta regra)."""
        viavel, _motivo, _carga_deck_maxima = AVALIADOR_ROTA_PADRAO.validar_cargas_petro(inst, k, seq)
        return viavel

    def registrar_convergencia(self, inst, iteracao, no_id, lb, ub, n_colunas, tempo, ub_mip_iter=None):
        if not hasattr(self, "melhor_ub"):
            self.melhor_ub = float("inf")

        # ub_mip_iter = MIP rodado especificamente nesta iteração (pode ser None)
        # ub = melhor UB vindo do MIP periódico (acumulado)
        ub_efetivo = ub_mip_iter if ub_mip_iter is not None else ub

        if ub_efetivo is not None and ub_efetivo < self.melhor_ub:
            self.melhor_ub = float(ub_efetivo)

        gap = None
        if self.melhor_ub < float("inf") and lb not in [None, 0]:
            gap = (self.melhor_ub - lb) / abs(lb)

        self.log_convergencia.append({
            "instancia": getattr(inst, "fileName", ""),
            "iteracao": iteracao,
            "no_id": no_id,
            "LB_frac": lb,
            "UB_mip_iter": ub_mip_iter,
            "UB_mip_periodico": ub,
            "melhor_UB": self.melhor_ub if self.melhor_ub < float("inf") else None,
            "gap_%": round(gap * 100, 4) if gap is not None else None,
            "n_colunas_pool": n_colunas,
            "tempo": tempo,
        })

    def coluna_ja_existe(self, seq, k=None, globalmente=True):
        chave = tuple(seq)

        if globalmente:
            for kk in self.rotas.keys():
                for seq_existente in self.rotas[kk]["sequencia_rota"]:
                    if tuple(seq_existente) == chave:
                        return True
        else:
            if k is None:
                return False

            for seq_existente in self.rotas[k]["sequencia_rota"]:
                if tuple(seq_existente) == chave:
                    return True

        return False


    def exportar_convergencia_excel(self, inst, usar_estabilizacao=True):
        import pandas as pd
        import os

        if not self.log_convergencia:
            print("Sem dados de convergencia")
            return

        modo = "COM_estab" if usar_estabilizacao else "SEM_estab"
        nome_arquivo = f"convergencia_{modo}_{inst.nbcd}.xlsx"

        df = pd.DataFrame(self.log_convergencia)

        instancia = inst.nomeInst.split("/")[-1].replace(".txt", "")

        # Identificador único por run: instância + gammas + iteraSemMelhora
        g_ini = int(getattr(self, "gamma_pi_inicial", 0))
        g_max = int(getattr(self, "gamma_pi_max", 0))
        sm    = int(getattr(inst, "iteraSemMelhora", 0))
        run_id = f"{instancia}_g{g_ini}_G{g_max}_SM{sm}"

        # Nome da aba limitado a 31 chars (limite do Excel)
        aba = run_id[:31]

        resumo = {
            "run_id":       run_id,
            "instancia":    instancia,
            "modo":         modo,
            "gamma_ini":    g_ini,
            "gamma_max":    g_max,
            "sem_melhora":  sm,
            "melhor_LB":    df["LB_frac"].dropna().iloc[-1] if df["LB_frac"].notna().any() else None,
            "melhor_UB":    df["melhor_UB"].dropna().min()  if df["melhor_UB"].notna().any() else None,
            "gap_final_%":  df["gap_%"].dropna().iloc[-1]   if "gap_%" in df.columns and df["gap_%"].notna().any() else None,
            "iteracoes":    df["iteracao"].max(),
            "n_colunas_final": df["n_colunas_pool"].iloc[-1] if "n_colunas_pool" in df.columns else None,
        }

        df_resumo = pd.DataFrame([resumo])

        if os.path.exists(nome_arquivo):
            with pd.ExcelWriter(nome_arquivo, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=aba, index=False)
                try:
                    antigo = pd.read_excel(nome_arquivo, sheet_name="resumo")
                    # remove linha anterior do mesmo run_id, se existir
                    if "run_id" in antigo.columns:
                        antigo = antigo[antigo["run_id"] != run_id]
                    else:
                        antigo = antigo[antigo["instancia"] != instancia]
                    novo_resumo = pd.concat([antigo, df_resumo], ignore_index=True)
                except Exception:
                    novo_resumo = df_resumo
                novo_resumo.to_excel(writer, sheet_name="resumo", index=False)
        else:
            with pd.ExcelWriter(nome_arquivo, engine="openpyxl") as writer:
                df_resumo.to_excel(writer, sheet_name="resumo", index=False)
                df.to_excel(writer, sheet_name=aba, index=False)

        print(f"Exportado: {nome_arquivo} | aba: {aba}")

    def travel_time(self, inst, i, j,k):
        return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade


    def printar_sol_exata(self, inst):
        print("=========INICIO PRINT SOLUCAO COMPACTO=========")
        custototal=0
        for k, dados in self.rotas.items():
            print(f"sol exata veic {k}")
            print("sequencia_rota =")
            pprint(dados.get('sequencia_rota', []))
            print("custo =")
            pprint(dados.get('custo', []))
            custototal += sum(dados.get('custo', []))
        print(f"CUSTO TOTAL COMPACTO = {custototal:.4f}")
        self.custo = custototal
        print("=========FIM PRINT SOLUCAO EXATA=========")

    def plotar_rota(self, inst, sequencia, k=0, pi=None, mu_arc=None,
                    titulo=None, mostrar_labels_nos=True,
                    mostrar_deposito_final_deslocado=True):


        if pi is None:
            pi = []
        if mu_arc is None:
            mu_arc = {}

        if sequencia is None or len(sequencia) < 2:
            print("Sequência inválida para plot.")
            return

        def coord(no_idx):
            x = inst.noh[no_idx].XCOORD
            y = inst.noh[no_idx].YCOORD

            # depósito final coincide com o inicial na sua instância
            # então desloca visualmente só para aparecer melhor
            if mostrar_deposito_final_deslocado and no_idx == inst.nbn - 1:
                x += 1.5
                y += 1.5
            return x, y

        def custo_real_arco(i, j):
            return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

        def dual_cliente(j):
            if 1 <= j <= inst.nbcd and len(pi) >= j:
                return pi[j - 1]
            return 0.0

        def dual_arco(i, j):
            if (i, j, k) in mu_arc:
                return mu_arc[(i, j, k)]
            if (i, j) in mu_arc:
                return mu_arc[(i, j)]
            return 0.0

        def custo_reduzido_arco(i, j):
            return custo_real_arco(i, j) - dual_cliente(j) - dual_arco(i, j)

        plt.figure(figsize=(11, 8))

        # plota todos os nós
        for idx, no in enumerate(inst.noh):
            x, y = coord(idx)

            if idx == 0:
                plt.scatter(x, y, s=180, marker='s', zorder=3, label='Depósito inicial')
            elif idx == inst.nbn - 1:
                plt.scatter(x, y, s=180, marker='^', zorder=3, label='Depósito final')
            else:
                plt.scatter(x, y, s=70, zorder=3)

            if mostrar_labels_nos:
                plt.text(x + 0.3, y + 0.3, str(idx), fontsize=9)

        # plota rota e custos nos arcos
        custo_total_real = 0.0
        custo_total_red_arcos = 0.0

        for t in range(len(sequencia) - 1):
            i = sequencia[t]
            j = sequencia[t + 1]

            xi, yi = coord(i)
            xj, yj = coord(j)

            # linha do arco
            plt.plot([xi, xj], [yi, yj], linewidth=2.0, alpha=0.85, zorder=2)

            cr = custo_real_arco(i, j)
            cred = custo_reduzido_arco(i, j)

            custo_total_real += cr
            custo_total_red_arcos += cred

            # ponto médio
            mx = (xi + xj) / 2.0
            my = (yi + yj) / 2.0

            # deslocamento perpendicular pequeno para separar os textos
            dx = xj - xi
            dy = yj - yi
            norma = (dx ** 2 + dy ** 2) ** 0.5
            if norma > 1e-9:
                offx = -dy / norma * 0.8
                offy = dx / norma * 0.8
            else:
                offx = 0.0
                offy = 0.0

            # azul = custo real
            plt.text(mx + offx, my + offy,
                     f"{cr:.2f}",
                     color='blue', fontsize=9,
                     bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="blue", alpha=0.7))

            # vermelho = custo reduzido
            plt.text(mx - offx, my - offy,
                     f"{cred:.2f}",
                     color='red', fontsize=9,
                     bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="red", alpha=0.7))

        if titulo is None:
            titulo = f"Rota veículo {k} | real={custo_total_real:.2f} | red(arcos)={custo_total_red_arcos:.2f}"

        plt.title(titulo)
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.grid(True, alpha=0.3)
        plt.axis("equal")
        plt.legend()
        plt.show()


    def exportar_json(self, inst, nome_arquivo="solucao.json"):
        """
        Exporta a solução atual (rotas, nós e tempos de chegada) para um arquivo JSON.
        Compatível com visualização em HTML com Leaflet.
        """
        dados = {
            "veiculos": [],
            "nos": []
        }

        # Adiciona os nós com coordenadas
        for node in inst.noh:
            dados["nos"].append({
                "id": node.id,
                "x": node.XCOORD,
                "y": node.YCOORD
            })

        # Adiciona as rotas dos veículos
        for k in self.rotas.keys():
            for p, rota in enumerate(self.rotas[k]['sequencia_rota']):
                chegada_por_no = []
                for i in rota:
                    chegada = inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0
                    chegada_por_no.append(chegada)

                dados["veiculos"].append({
                    "id": k,
                    "rota": rota,
                    "custo": self.rotas[k]['custo'][p],
                    "chegadas": chegada_por_no
                })

        # Salva em arquivo JSON
        with open(nome_arquivo, 'w') as f:
            json.dump(dados, f, indent=4)

        print(f"✅ Solução exportada com sucesso para '{nome_arquivo}'")


    def exportar_json_gc(self, inst, nome_arquivo="solucao_gc.json"):
        """
        Exporta apenas as rotas escolhidas (lambda ≈ 1) da GC para visualização no mapa.
        """
        dados = {
            "veiculos": [],
            "nos": []
        }

        # Adiciona os nós com coordenadas
        for node in inst.noh:
            dados["nos"].append({
                "id": node.id,
                "x": node.XCOORD,
                "y": node.YCOORD
            })

        # Adiciona apenas as rotas escolhidas
        for k in self.rotas_escolhidas:
            for idx, rota in enumerate(self.rotas_escolhidas[k]['sequencias']):
                chegada_por_no = []
                for i in rota:
                    chegada = inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0
                    chegada_por_no.append(chegada)

                dados["veiculos"].append({
                    "id": k,
                    "rota": rota,
                    "custo": self.rotas_escolhidas[k]['custos'][idx],
                    "chegadas": chegada_por_no
                })

        with open(nome_arquivo, 'w') as f:
            json.dump(dados, f, indent=4)

        print(f" Solução GC exportada com sucesso para '{nome_arquivo}'")



    def registrar_fo_gc(self, inst, valor_fo):


        return

    # INICIO para os arquivos de saida
    def sequencias_exato_para_texto(self):
        partes = []

        for k in sorted(self.rotas.keys()):
            seqs = self.rotas[k].get("sequencia_rota", [])
            txt_seqs = ["[" + ",".join(map(str, seq)) + "]" for seq in seqs]
            partes.append(f"V{k}: " + " | ".join(txt_seqs))

        return " ; ".join(partes) if partes else "SEM_SEQUENCIA_EXATO"

    def sequencias_bp_para_texto(self):
        partes = []

        if not hasattr(self, "rotas_escolhidas") or not self.rotas_escolhidas:
            return "SEM_SEQUENCIA_BP"

        for k in sorted(self.rotas_escolhidas.keys()):
            seqs = self.rotas_escolhidas[k].get("sequencias", [])
            txt_seqs = ["[" + ",".join(map(str, seq)) + "]" for seq in seqs]
            partes.append(f"V{k}: " + " | ".join(txt_seqs))

        return " ; ".join(partes) if partes else "SEM_SEQUENCIA_BP"

    # FIM para os arquivos de saida

    def inserir_cliente_rota(self, inst, k, cliente, pos):
        """
        LEGADO: nao usada pelo pipeline ativo (unica chamadora e
        Metodos.geracao_colunas, que por sua vez nao e invocada por
        branch_and_price_global). Logica Solomon equivalente a
        AvaliadorRota.avaliar_rota_solomon; mantida standalone (nao
        delegada) para preservar seu contrato de retorno ('s'/'u' por
        posicao) sem cobertura de teste.

        Insere `cliente` na rota do veículo k na posição pos.
        Atualiza tempos e carga. Testa viabilidade (janelas e capacidade).
        """
        rota_seq = self.rotas[k]['sequencia_rota'][0]  # ou índice da rota ativa

        if not (1 <= pos <= len(rota_seq) - 1):
            return {'factivel': False, 'motivo': 'posicao'}
        if cliente in rota_seq:
            return {'factivel': False, 'motivo': 'duplicado', 'no': cliente}

        nova = rota_seq[:pos] + [cliente] + rota_seq[pos:]

        def ready(i):
            return inst.noh[i].READY_TIME[0] if inst.noh[i].READY_TIME else 0

        def due(i):
            return inst.noh[i].DUE_DATE[0] if inst.noh[i].DUE_DATE else 1e9

        def service(i):
            return inst.noh[i].SERVICE_TIME[0] if inst.noh[i].SERVICE_TIME else 0

        def demand(i):
            return getattr(inst.noh[i], 'DEMAND', 0.0)

        def travel(i, j):
            return inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade

        Q = inst.veiculos[k].capacidade
        s = [0.0] * len(nova)
        u = [0.0] * len(nova)

        s[0] = 0.0
        u[0] = 0.0

        for idx in range(1, len(nova)):
            i, j = nova[idx - 1], nova[idx]
            s[idx] = max(ready(j), s[idx - 1] + service(i) + travel(i, j))
            if s[idx] > due(j):
                return {'factivel': False, 'motivo': 'janela', 'no': j}

            u[idx] = u[idx - 1] + demand(j)
            if u[idx] > Q:
                return {'factivel': False, 'motivo': 'capacidade', 'no': j}

        custo_antigo = sum(travel(rota_seq[i], rota_seq[i + 1]) for i in range(len(rota_seq) - 1))
        custo_novo = sum(travel(nova[i], nova[i + 1]) for i in range(len(nova) - 1))
        delta = custo_novo - custo_antigo

        return {'factivel': True, 'rota': nova, 's': s, 'u': u, 'delta_custo': delta}

    def exportar_rotas_selecionadas_js(
            self,
            inst,
            indices,
            veiculos,
            pi=None,
            mu_arc=None,
            sigma=None,
            nome_arquivo_js="rotas_plot_data.js",
            title="Comparação de rotas",
            subtitle="Arquivo gerado automaticamente."
    ):
        import json

        if pi is None:
            pi = []
        if mu_arc is None:
            mu_arc = {}
        if sigma is None:
            sigma = {}

        cores = [
            "#2563eb", "#ef4444", "#0f766e", "#7c3aed", "#ea580c",
            "#0891b2", "#65a30d", "#db2777", "#1d4ed8", "#9333ea"
        ]

        def coord(i):
            return float(inst.noh[i].XCOORD), float(inst.noh[i].YCOORD)

        def custo_real_arco(i, j, k):
            return float(inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade)

        def dual_cliente(j):
            if 1 <= j <= inst.nbcd and len(pi) >= j:
                return float(pi[j - 1])
            return 0.0

        def dual_arco(i, j, k):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            if (i, j) in mu_arc:
                return float(mu_arc[(i, j)])
            return 0.0

        def sigma_k(k):
            if isinstance(sigma, dict):
                return float(sigma.get(k, 0.0))
            if isinstance(sigma, (list, tuple)):
                return float(sigma[k]) if k < len(sigma) else 0.0
            try:
                return float(sigma)
            except:
                return 0.0

        routes = []
        route_id = 0

        for k in veiculos:
            if k not in self.rotas:
                continue

            seqs = self.rotas[k].get("sequencia_rota", [])

            for p in indices:
                if p < 0 or p >= len(seqs):
                    continue

                sequencia = seqs[p]

                nodes = []
                for no in sequencia:
                    x, y = coord(no)

                    if no == 0:
                        kind = "depot_start"
                    elif no == inst.nbn - 1:
                        kind = "depot_end"
                    else:
                        kind = "customer"

                    nodes.append({
                        "id": int(no),
                        "x": x,
                        "y": y,
                        "kind": kind
                    })

                arcs = []
                total_real = 0.0
                total_red_sem_sigma = 0.0

                for t in range(len(sequencia) - 1):
                    i = sequencia[t]
                    j = sequencia[t + 1]

                    xi, yi = coord(i)
                    xj, yj = coord(j)

                    cr = custo_real_arco(i, j, k)
                    cred = cr - dual_cliente(j) - dual_arco(i, j, k)

                    total_real += cr
                    total_red_sem_sigma += cred

                    arcs.append({
                        "from": int(i),
                        "to": int(j),
                        "from_x": xi,
                        "from_y": yi,
                        "to_x": xj,
                        "to_y": yj,
                        "real_cost": round(cr, 6),
                        "reduced_cost": round(cred, 6)
                    })

                routes.append({
                    "id": route_id,
                    "name": f"Rota p={p} veic={k}",
                    "vehicle": int(k),
                    "sequence": [int(x) for x in sequencia],
                    "total_real_cost": round(total_real, 6),
                    "total_reduced_cost": round(total_red_sem_sigma - sigma_k(k), 6),
                    "nodes": nodes,
                    "arcs": arcs,
                    "color": cores[route_id % len(cores)]
                })

                route_id += 1

        data = {
            "title": title,
            "subtitle": subtitle,
            "routes": routes
        }

        with open(nome_arquivo_js, "w", encoding="utf-8") as f:
            f.write("window.ROUTE_PLOT_DATA = ")
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write(";\n")

        print(f"JS exportado: {nome_arquivo_js} | rotas={len(routes)}")

    def exportar_rotas_pares_js(
            self,
            inst,
            selecao,
            pi=None,
            mu_arc=None,
            sigma=None,
            nome_arquivo_js="rotas_plot_data.js",
            title="Comparação de rotas",
            subtitle="Arquivo gerado automaticamente."
    ):
        import json

        if pi is None:
            pi = []
        if mu_arc is None:
            mu_arc = {}
        if sigma is None:
            sigma = {}

        cores = [
            "#2563eb", "#ef4444", "#0f766e", "#7c3aed", "#ea580c",
            "#0891b2", "#65a30d", "#db2777", "#1d4ed8", "#9333ea"
        ]

        def coord(i):
            return float(inst.noh[i].XCOORD), float(inst.noh[i].YCOORD)

        def custo_real_arco(i, j, k):
            return float(inst.matriz_distancia[i][j] / inst.veiculos[k].velocidade)

        def dual_cliente(j):
            if 1 <= j <= inst.nbcd and len(pi) >= j:
                return float(pi[j - 1])
            return 0.0

        def dual_arco(i, j, k):
            if (i, j, k) in mu_arc:
                return float(mu_arc[(i, j, k)])
            if (i, j) in mu_arc:
                return float(mu_arc[(i, j)])
            return 0.0

        def sigma_k(k):
            if isinstance(sigma, dict):
                return float(sigma.get(k, 0.0))
            if isinstance(sigma, (list, tuple)):
                return float(sigma[k]) if k < len(sigma) else 0.0
            try:
                return float(sigma)
            except:
                return 0.0

        routes = []

        for rid, item in enumerate(selecao):
            k = int(item["k"])
            p = int(item["p"])

            if k not in self.rotas:
                continue

            seqs = self.rotas[k].get("sequencia_rota", [])
            if p < 0 or p >= len(seqs):
                continue

            sequencia = seqs[p]

            nodes = []
            for no in sequencia:
                x, y = coord(no)
                if no == 0:
                    kind = "depot_start"
                elif no == inst.nbn - 1:
                    kind = "depot_end"
                else:
                    kind = "customer"

                noh = inst.noh[no]

                ready = noh.READY_TIME[0] if getattr(noh, "READY_TIME", None) else 0.0
                due = noh.DUE_DATE[0] if getattr(noh, "DUE_DATE", None) else 1e9
                service = noh.SERVICE_TIME[0] if getattr(noh, "SERVICE_TIME", None) else 0.0

                nodes.append({
                    "id": int(no),
                    "x": x,
                    "y": y,
                    "kind": kind,
                    "ready_time": float(ready),
                    "due_date": float(due),
                    "service_time": float(service)
                })

            arcs = []
            total_real = 0.0
            total_red_sem_sigma = 0.0

            for t in range(len(sequencia) - 1):
                i = sequencia[t]
                j = sequencia[t + 1]

                xi, yi = coord(i)
                xj, yj = coord(j)

                cr = custo_real_arco(i, j, k)
                cred = cr - dual_cliente(j) - dual_arco(i, j, k)

                total_real += cr
                total_red_sem_sigma += cred

                arcs.append({
                    "from": int(i),
                    "to": int(j),
                    "from_x": xi,
                    "from_y": yi,
                    "to_x": xj,
                    "to_y": yj,
                    "real_cost": round(cr, 6),
                    "reduced_cost": round(cred, 6)
                })

            routes.append({
                "id": rid,
                "name": item.get("nome", f"Rota p={p} veic={k}"),
                "vehicle": int(k),
                "sequence": [int(x) for x in sequencia],
                "total_real_cost": round(total_real, 6),
                "total_reduced_cost": round(total_red_sem_sigma - sigma_k(k), 6),
                "nodes": nodes,
                "arcs": arcs,
                "color": item.get("color", cores[rid % len(cores)])
            })

        data = {
            "title": title,
            "subtitle": subtitle,
            "routes": routes
        }

        with open(nome_arquivo_js, "w", encoding="utf-8") as f:
            f.write("window.ROUTE_PLOT_DATA = ")
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write(";\n")

        print(f"JS exportado: {nome_arquivo_js} | rotas={len(routes)}")
