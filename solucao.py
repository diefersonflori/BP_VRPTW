import json
from pprint import pprint
import os
import csv
import instancia
#import matplotlib.pyplot as plt
import json


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

        self.construtivas = [0, 0, 0, 0, 0]
        self.TIME_MAX = 360000


        #para gerar o grafico -exportar convergencia
        self.log_convergencia = []
        self.melhor_ub = float("inf")
        self.iter_gc = 5
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

    time_initial = 0
    FO_TARGET = -1
    TIME_TARGET = 99999999

    def registrar_convergencia(self, inst, iteracao, no_id, lb, ub, n_colunas, tempo):
        if not hasattr(self, "melhor_ub"):
            self.melhor_ub = float("inf")

        if ub is not None and ub < self.melhor_ub:
            self.melhor_ub = float(ub)

        gap = None
        if self.melhor_ub < float("inf") and lb not in [None, 0]:
            gap = (self.melhor_ub - lb) / abs(lb)

        self.log_convergencia.append({
            "instancia": getattr(inst, "fileName", ""),
            "iteracao": iteracao,
            "no_id": no_id,
            "LB_frac": lb,
            "UB_mip_iteracao": ub,
            "melhor_UB": self.melhor_ub if self.melhor_ub < float("inf") else None,
            "gap": gap,
            "n_colunas": n_colunas,
            "tempo": tempo,
        })

    def exportar_convergencia_excel(self, inst, nome_arquivo=None):
        import pandas as pd
        import os

        if not self.log_convergencia:
            print("Sem dados de convergência")
            return

        nome_arquivo = f"convergencia_bp_{inst.nbcd}v.xlsx"

        df = pd.DataFrame(self.log_convergencia)

        if "gap" in df.columns:
            df["gap_%"] = df["gap"] * 100

        instancia = inst.nomeInst.split("/")[-1].replace(".txt", "")
        aba = instancia[:31]

        resumo = {
            "instancia": instancia,
            "melhor_LB": df["LB_frac"].dropna().iloc[-1] if df["LB_frac"].notna().any() else None,
            "melhor_UB": df["melhor_UB"].dropna().min() if df["melhor_UB"].notna().any() else None,
            "gap_final_%": df["gap_%"].dropna().iloc[-1] if "gap_%" in df and df["gap_%"].notna().any() else None,
            "iteracoes": df["iteracao"].max(),
            "n_colunas_final": df["n_colunas"].iloc[-1],
        }

        df_resumo = pd.DataFrame([resumo])

        if os.path.exists(nome_arquivo):
            with pd.ExcelWriter(nome_arquivo, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=aba, index=False)

                try:
                    antigo = pd.read_excel(nome_arquivo, sheet_name="resumo")
                    antigo = antigo[antigo["instancia"] != instancia]
                    novo_resumo = pd.concat([antigo, df_resumo], ignore_index=True)
                except:
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
