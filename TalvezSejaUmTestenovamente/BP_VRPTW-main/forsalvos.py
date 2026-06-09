            for k in  range(1): # sol_pool.rotas.keys(): ## frota homogenea
                proibidos_k = {(i, j) for (i, j, kk) in no_bp.arcos_proibidos if kk == k}
                fixados_k = {(i, j) for (i, j, kk) in no_bp.arcos_fixados_em_1 if kk == k}
                proibidos_equiv = self.proibidos_com_fixados(inst, proibidos_k, fixados_k)
                mu_arc = mu_arc_por_k.get(k, {})

                t0 = time.time()
                nova_rota=None


                if(inst.nbconstrutiva!=0 and inst.nbconstrutiva!=22): #22 é arbitrario para testar o ultimo so
                    nova_rota, custo_red = self.SUB_VNSRANDOM(inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc)
                    if nova_rota is not None:
                        sol_pool.construtivas[0] += 1
                        print("gerou na 1")




                if (inst.nbconstrutiva != 1 and inst.nbconstrutiva!=22):
                    if nova_rota is None:
                        nova_rota, custo_red = self.SUB_HEUR_ALLBESTINSERTION(
                            inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                        )
                        if nova_rota is not None:
                            sol_pool.construtivas[1] += 1
                            if (self.printarsol):
                                print("gerou na 2")

                if (inst.nbconstrutiva != 2 and inst.nbconstrutiva!=22):
                    if nova_rota is None:
                        nova_rota, custo_red = self.SUB_HEUR_VNS( #é o VNS com um chorinho pra quem está indo bem
                            inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                        )
                        if nova_rota is not None:
                            sol_pool.construtivas[2] += 1
                            if (self.printarsol):
                                print("gerou na 3")


                if (inst.nbconstrutiva != 3 ):
                    if nova_rota is None:
                        if (self.printarsol):
                            print("%%%%%%%%%TESTE BIDIRECIONAL")
                        nova_rota, custo_red = self.SUB_PROG_DIN_BIDIRECIONAL(
                            inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                        )
                        """
                        if nova_rota is not None:
                            nova_rota["custo_reduzido"] = float(custo_red)
                            print(f"NOVA COLUNA GERAL | rc={nova_rota['custo_reduzido']:.6f}")
                            print(nova_rota)
                        """


                        """
                        nova_rota, custo_red = self.SUB_PROG_DIN_BIDIRECIONAL_DEPTH(
                            inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp,
                            max_depth=4,
                            usar_poda_por_no=False,
                            usar_poda_profundidade=True
                        )
                        """

                        if (self.printarsol):
                            print("%%%%%%% BIDIRECIONALACHOU")
                        if nova_rota is not None:
                            sol_pool.construtivas[3] += 1
                            if (self.printarsol):
                                print("gerou na BID")


                """"""

                if nova_rota is None:
                    print("$$$$$$$$$$$$$$ nao achou sol, testa PDMICHEL")
                    nova_rota, custo_red = self.SUB_PROG_DIN_BIDIRECIONAL_MICHEL(
                        inst,
                        pi,
                        sigma_k=sigma[k],
                        k=k,
                        NO_BP=no_bp,
                        max_labels_por_no=100,
                        usar_poda_por_no=True,
                        usar_bound_tempo=True,
                        frac_tempo_critico=0.5,
                        modo="heur"
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[4] += 1
                        print("gerou na PD MICHEL")

                #"""
                if nova_rota is None or  float(custo_red) >= -EPS_RC:
                    print("$$$$$$$$$$$$$$ nao achou sol, testa PD")
                    nova_rota, custo_red = self.SUB_PROG_DIN_PW(
                        inst, pi, sigma_k=sigma[k], k=k, NO_BP=no_bp, mu_arc=mu_arc
                    )
                    if nova_rota is not None:
                        sol_pool.construtivas[5] += 1
                        print("gerou na PD COMPLETA")
                #"""




                if iter_cg == 13:
                    print("")

                if nova_rota is None:
                    print("PASSOU PELOS 3 sem gerar nada")
                    continue

                nova_rota["custo_reduzido"] = float(custo_red)
                print(f"NOVA COLUNA GERAL | rc={nova_rota['custo_reduzido']:.6f}")
                print(nova_rota)

                if float(custo_red) < -EPS_RC:
                    seq = nova_rota["clientes"]
                    if not self.coluna_respeita_no(no_bp, seq, k):
                        continue

                    novas_colunas.append((k, seq, nova_rota["bin_xij"], nova_rota["custo"]))

                    print(f"NOVA COLUNA | rc={nova_rota['custo_reduzido']:.6f}")
                    print(nova_rota)
                    print("")

                    #""" TABOOOOOO
                    mat = no_bp.tabu_until[k]
                    for i in range(inst.nbn):
                        row = mat[i]
                        for j in range(inst.nbn):
                            if row[j] > 0:
                                row[j] -= 1



                    for t in range(len(seq) - 1):
                        i, j = seq[t], seq[t + 1]
                        no_bp.freq_arc[k][i][j] += 1
                        no_bp.last_arc[k][i][j] = iter_cg
                        no_bp.tabu_until[k][i][j] = no_bp.tabu_tenure
                    #"""

                    ###
                    print("")
                    with open(nome_arquivo_logLOCAL, "a", encoding="utf-8") as f:
                        f.write(
                            f"   adicionou coluna | veic={k} | idx={no_bp.id_no} | rc={custo_red:.6f} | rota={nova_rota}\n")

