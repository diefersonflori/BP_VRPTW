import json
from pprint import pprint
import os
import csv
import instancia

class Solucao:
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

        print(f"✅ Solução GC exportada com sucesso para '{nome_arquivo}'")



    def registrar_fo_gc(self, inst, valor_fo):

        filename = f"{inst.nbcd}.csv"

        with open(filename, "a", newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["COMPACTO", f"{valor_fo:.6f}"])

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