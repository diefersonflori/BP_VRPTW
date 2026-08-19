// ============================================================================
// BID_SILVA_CPP: pricing HEURISTICO Silva (beam/label-setting com dominancia
// por nivel) em C++, reproduzindo a MESMA ideia de SUB_PROG_BID_SILVA
// (metodos.py, NAO alterada por esta tarefa). Referencia estrutural oficial:
// SUB_PROG_BID_SILVA.
//
// Reuso do nucleo (silva_pricing_core.h, NAO alterado por este arquivo):
// toda a fisica/oraculo (SilvaPricingData::avaliar_fechamento, mesma formula
// de avaliar_rota_silva2024) e todo o branching/nao-revisita/precedencia/
// capacidades (SilvaPricingData::arco_permitido/contem_todos_fixados, e a
// mesma logica de mascara/plataforma-fechada/entrega-iniciada/deck-diesel-
// agua ja usada por PD_SILVA_CPP.cpp) vem exclusivamente do nucleo
// SilvaPricingData -- nada disso e reimplementado aqui. O unico codigo
// especifico deste arquivo e a ESTRATEGIA DE BUSCA (beam por nivel,
// candidata registrada so quando RC<0, proxy de ranking herdado do pai
// quando o fechamento imediato nao e viavel/permitido).
//
// BidLabel (struct local, NAO em silva_pricing_core.h): mesmos campos de
// silva::SilvaLabel + rc_fechamento (proxy de ranking do beam, exclusivo do
// BID -- nao faz parte do estado fisico/branching, so da heuristica de
// busca). Definido aqui (nao no header) para nao alterar SilvaLabel usado
// por PD_SILVA_CPP.cpp -- ZERO mudancas em silva_pricing_core.h nesta
// tarefa.
//
// FECHAR != CONTINUAR (mesma secao 5/9 da tarefa anterior, mesma correcao
// critica documentada em SUB_PROG_BID_SILVA): a cada expansao, o label
// prossegue para o proximo nivel INDEPENDENTE de conseguir fechar uma
// candidata agora. avaliar_fechamento (fisica) e arco_permitido(ultimo,
// depf)+contem_todos_fixados (branching, dentro de `registra`) sao
// checados em momentos SEPARADOS -- nunca usados para podar a expansao.
//
// Beam: ao final de cada nivel, so os `max_labels_por_no` labels de menor
// rc_fechamento sobrevivem -- EXCETO labels cujo ultimo no tem uma
// continuacao obrigatoria pendente (succ_fixo), que NUNCA sao removidos por
// ranking (mesma protecao ja validada no BID Python -- ver docstring de
// SUB_PROG_BID_SILVA).
//
// completa=False SEMPRE (BID e heuristico, nunca certifica ausencia de
// coluna negativa -- secao 2 da tarefa). timeout/max_total_labels sao SO um
// teto de seguranca defensivo (nao existe no BID Python, que so usa
// max_labels_por_no/max_depth/max_candidatas) para o caso patologico de
// muitos labels "protegidos" (succ_fixo) se acumularem sem poda -- com os
// defaults desta tarefa (beam=60, depth<=nbcd) nao deveria disparar.
// ============================================================================

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <vector>
#include <string>
#include <chrono>
#include <algorithm>
#include <limits>

#include "silva_pricing_core.h"

namespace py = pybind11;

namespace {

struct BidLabel {
    int no = -1;
    std::bitset<silva::MAX_ORDERS> mask;
    int plataforma_aberta = -1;
    std::bitset<silva::MAX_PLATAFORMAS> fechadas;
    bool entrega_iniciada = false;
    double deck = 0.0, diesel = 0.0, agua = 0.0;
    int pai = -1;
    int profundidade = 0;
    double rc_fechamento = std::numeric_limits<double>::infinity();
};

std::vector<int> reconstruir_sequencia_bid(const std::vector<BidLabel>& pool, int idx) {
    std::vector<int> seq;
    while (idx != -1) {
        seq.push_back(pool[(size_t)idx].no);
        idx = pool[(size_t)idx].pai;
    }
    std::reverse(seq.begin(), seq.end());
    return seq;
}

} // namespace

py::tuple pricing_bid_silva(
    // ---- estrutura ----
    int nbn, int nbcd, int dep0, int depf, int k,
    // ---- navegacao ----
    py::array_t<double, py::array::c_style | py::array::forcecast> dist_km_arr,
    double v_low, double v_high, double th_km, double safe_positioning_time,
    std::vector<int> plataforma_id,
    std::vector<double> set_por_plataforma,
    // ---- tempo/servico/janelas ----
    std::vector<double> servico,
    std::vector<std::vector<double>> ready,
    std::vector<std::vector<double>> due,
    // ---- recursos por no ----
    std::vector<double> deck_load,
    std::vector<double> deck_backload,
    std::vector<double> diesel_dem,
    std::vector<double> agua_dem,
    std::vector<double> tempo_carreg_deck,
    std::vector<double> tempo_carreg_diesel,
    std::vector<double> tempo_carreg_agua,
    std::vector<double> tempo_descarreg_backload,
    std::vector<std::uint8_t> is_backload,
    std::vector<double> order_due_time,
    std::vector<std::uint8_t> has_due_time,
    // ---- capacidades do navio ----
    double cap_deck, double cap_diesel, double cap_agua,
    // ---- fisica do navio/FO ----
    double AT, double max_partida, double tdl,
    double theta_k, double varphi_k, double gamma_k, double delta_k,
    double xi_usado, double alpha_fo, double eta_fo,
    // ---- duais (mestre) ----
    std::vector<double> pi,
    double sigma_k,
    std::vector<double> mu_flat,
    // ---- branching ----
    std::vector<std::uint8_t> forbid_flat,
    std::vector<int> req_i,
    std::vector<int> req_j,
    // ---- estrategia BID (secao 6/7/10 do pedido) ----
    int max_labels_por_no,
    int max_depth,
    int max_candidatas,
    double eps,
    // ---- teto de seguranca defensivo (NAO existe no BID Python; ver
    // comentario no topo do arquivo) ----
    long long max_total_labels,
    double timeout_s
) {
    auto t_inicio = std::chrono::steady_clock::now();

    if (dist_km_arr.ndim() != 2)
        throw std::runtime_error("dist_km_arr deve ser 2D (nbn x nbn)");
    auto Dm = dist_km_arr.unchecked<2>();
    if ((int)Dm.shape(0) != nbn || (int)Dm.shape(1) != nbn)
        throw std::runtime_error("dist_km_arr deve ser nbn x nbn");

    if (max_depth <= 0) max_depth = nbcd;

    // ---- monta o nucleo reutilizavel (silva_pricing_core.h) -- IDENTICO ao
    // marshaling de pricing_pd_silva em PD_SILVA_CPP.cpp (nao factorado num
    // helper comum de proposito, para NAO alterar PD_SILVA_CPP.cpp) ----
    silva::SilvaPricingData data;
    data.nbn = nbn; data.nbcd = nbcd; data.dep0 = dep0; data.depf = depf;
    data.dist_km.assign((size_t)nbn, std::vector<double>((size_t)nbn, 0.0));
    for (int i = 0; i < nbn; ++i)
        for (int j = 0; j < nbn; ++j)
            data.dist_km[(size_t)i][(size_t)j] = Dm(i, j);
    data.v_low = v_low; data.v_high = v_high; data.th_km = th_km;
    data.safe_positioning_time = safe_positioning_time;
    data.plataforma_id = plataforma_id;
    data.set_por_plataforma = set_por_plataforma;
    data.servico = servico;
    data.ready = ready;
    data.due = due;
    data.deck_load = deck_load;
    data.deck_backload = deck_backload;
    data.diesel_dem = diesel_dem;
    data.agua_dem = agua_dem;
    data.tempo_carreg_deck = tempo_carreg_deck;
    data.tempo_carreg_diesel = tempo_carreg_diesel;
    data.tempo_carreg_agua = tempo_carreg_agua;
    data.tempo_descarreg_backload = tempo_descarreg_backload;
    data.is_backload = is_backload;
    data.order_due_time = order_due_time;
    data.has_due_time = has_due_time;
    data.cap_deck = cap_deck; data.cap_diesel = cap_diesel; data.cap_agua = cap_agua;
    data.AT = AT; data.max_partida = max_partida; data.tdl = tdl;
    data.theta_k = theta_k; data.varphi_k = varphi_k; data.gamma_k = gamma_k; data.delta_k = delta_k;
    data.xi_usado = xi_usado; data.alpha_fo = alpha_fo; data.eta_fo = eta_fo;
    data.forbid_flat = forbid_flat;

    if ((int)req_i.size() != (int)req_j.size())
        throw std::runtime_error("req_i e req_j devem ter o mesmo tamanho");
    for (size_t t = 0; t < req_i.size(); ++t) {
        int i = req_i[t], j = req_j[t];
        auto its = data.succ_fixo.find(i);
        if (its != data.succ_fixo.end() && its->second != j)
            return py::make_tuple(py::list(), false, false, 0, 0, 0.0);
        auto itp = data.pred_fixo.find(j);
        if (itp != data.pred_fixo.end() && itp->second != i)
            return py::make_tuple(py::list(), false, false, 0, 0, 0.0);
        data.succ_fixo[i] = j;
        data.pred_fixo[j] = i;
    }

    if (mu_flat.empty()) mu_flat.assign((size_t)nbn * (size_t)nbn, 0.0);
    auto mu = [&](int i, int j) -> double {
        return mu_flat[(size_t)i * (size_t)nbn + (size_t)j];
        };
    auto rc_de = [&](double custo_real, const std::vector<int>& seq_fechada) -> double {
        double rc = custo_real;
        for (int c : seq_fechada) {
            if (c >= 1 && c <= nbcd) rc -= pi[(size_t)(c - 1)];
        }
        rc -= sigma_k;
        for (size_t t = 0; t + 1 < seq_fechada.size(); ++t) rc -= mu(seq_fechada[t], seq_fechada[t + 1]);
        return rc;
        };

    // ---- candidatas: mesma politica top-N por substituicao de
    // PD_SILVA_CPP.cpp (MAX_CANDIDATAS limita so o RETORNO, nunca a busca --
    // secao 10 do pedido: "as melhores encontradas, nao as primeiras") ----
    struct CandidataMulti { std::vector<int> seq; double custo; double rc; };
    std::vector<CandidataMulti> candidatas;
    int max_cand_efetivo = std::max(1, max_candidatas);

    auto registra = [&](const std::vector<int>& seq_fechada, double custo, double rc) {
        if (rc >= -eps) return;
        int penult = seq_fechada[seq_fechada.size() - 2];
        if (!data.arco_permitido(penult, depf)) return;
        if (!data.contem_todos_fixados(seq_fechada)) return;

        if ((int)candidatas.size() < max_cand_efetivo) {
            candidatas.push_back({ seq_fechada, custo, rc });
            return;
        }
        size_t pior_idx = 0;
        double pior_rc = candidatas[0].rc;
        for (size_t z = 1; z < candidatas.size(); ++z) {
            if (candidatas[z].rc > pior_rc) { pior_rc = candidatas[z].rc; pior_idx = z; }
        }
        if (rc < pior_rc) candidatas[pior_idx] = { seq_fechada, custo, rc };
        };

    // ---- pool de labels (parent-index + ultimo no, mesma politica de
    // memoria de PD_SILVA_CPP.cpp) ----
    std::vector<BidLabel> pool;
    pool.reserve(4096);

    BidLabel l0;
    l0.no = dep0; l0.pai = -1; l0.profundidade = 0;
    pool.push_back(l0);
    long long total_labels = 1;

    // avalia_fechamento_fisico (Python): SO fisica, NUNCA checa
    // arco_permitido(last, depf) aqui -- essa checagem de branching e feita
    // exclusivamente dentro de `registra`. Retorna par (viavel, custo, rc).
    auto avalia_fechamento_fisico = [&](int idx_label) -> std::tuple<bool, double, double, std::vector<int>> {
        std::vector<int> seq_fechada = reconstruir_sequencia_bid(pool, idx_label);
        seq_fechada.push_back(depf);
        auto res = data.avaliar_fechamento(seq_fechada);
        if (!res.viavel) return { false, 0.0, 0.0, seq_fechada };
        double rc = rc_de(res.custo, seq_fechada);
        return { true, res.custo, rc, seq_fechada };
        };

    {
        auto [viavel0, custo0, rc0, seq0] = avalia_fechamento_fisico(0);
        if (viavel0) {
            registra(seq0, custo0, rc0);
            pool[0].rc_fechamento = rc0;
        }
    }

    std::vector<int> nivel_atual = { 0 };
    int nivel = 0;
    bool timeout_flag = false;

    auto orcamento_esgotado = [&]() -> bool {
        if (total_labels >= max_total_labels) return true;
        double decorrido = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_inicio).count();
        if (decorrido > timeout_s) { timeout_flag = true; return true; }
        return false;
        };

    bool limite_atingido = false;

    while (nivel < max_depth && !nivel_atual.empty() && (int)candidatas.size() < max_cand_efetivo
        && !limite_atingido) {
        std::vector<int> proximo_nivel;
        proximo_nivel.reserve(nivel_atual.size() * 4);

        for (int lab_idx : nivel_atual) {
            if ((int)candidatas.size() >= max_cand_efetivo) break;
            if (orcamento_esgotado()) { limite_atingido = true; break; }

            BidLabel lab = pool[(size_t)lab_idx];
            int last = lab.no;

            for (int j = 1; j <= nbcd; ++j) {
                if (lab.mask.test((size_t)(j - 1))) continue;
                int pj = data.plataforma_id[(size_t)j];
                if (pj >= 0 && lab.fechadas.test((size_t)pj)) continue;
                if (!data.arco_permitido(last, j)) continue;

                bool nova_entrega_iniciada = lab.entrega_iniciada;
                int nova_plataforma_aberta = lab.plataforma_aberta;
                std::bitset<silva::MAX_PLATAFORMAS> nova_fechadas = lab.fechadas;
                if (pj != lab.plataforma_aberta) {
                    if (lab.plataforma_aberta >= 0) nova_fechadas.set((size_t)lab.plataforma_aberta);
                    nova_plataforma_aberta = pj;
                    nova_entrega_iniciada = false;
                }

                bool tem_coleta = data.deck_backload[(size_t)j] > 1e-9;
                bool tem_entrega = data.deck_load[(size_t)j] > 1e-9;
                if (tem_coleta && nova_entrega_iniciada) continue;
                if (tem_entrega) nova_entrega_iniciada = true;

                double novo_deck = lab.deck + data.deck_load[(size_t)j];
                if (novo_deck > cap_deck + 1e-6) continue;
                double novo_diesel = lab.diesel + data.diesel_dem[(size_t)j];
                if (std::isfinite(cap_diesel) && novo_diesel > cap_diesel + 1e-6) continue;
                double novo_agua = lab.agua + data.agua_dem[(size_t)j];
                if (std::isfinite(cap_agua) && novo_agua > cap_agua + 1e-6) continue;

                if (orcamento_esgotado()) { limite_atingido = true; break; }

                BidLabel novo;
                novo.no = j;
                novo.mask = lab.mask;
                novo.mask.set((size_t)(j - 1));
                novo.plataforma_aberta = nova_plataforma_aberta;
                novo.fechadas = nova_fechadas;
                novo.entrega_iniciada = nova_entrega_iniciada;
                novo.deck = novo_deck; novo.diesel = novo_diesel; novo.agua = novo_agua;
                novo.pai = lab_idx;
                novo.profundidade = lab.profundidade + 1;

                int idx_novo = (int)pool.size();
                pool.push_back(novo);
                total_labels++;

                // FECHAR != CONTINUAR: tentativa de fechar agora, NUNCA um
                // criterio para descartar o label -- o label ja foi
                // anexado ao proximo nivel independente do resultado.
                auto [viavel, custo, rc, seq_fechada] = avalia_fechamento_fisico(idx_novo);
                if (viavel) {
                    registra(seq_fechada, custo, rc);
                    pool[(size_t)idx_novo].rc_fechamento = rc;
                } else {
                    // Nao fechavel agora (fisica) -- herda o proxy de
                    // ranking do PAI (nunca inventa FO nova), so para
                    // ordenar o beam, nunca para decidir viabilidade.
                    pool[(size_t)idx_novo].rc_fechamento = lab.rc_fechamento;
                }

                proximo_nivel.push_back(idx_novo);

                if ((int)candidatas.size() >= max_cand_efetivo) break;
            }
            if (limite_atingido) break;
        }

        // ---- beam/dominancia por nivel (secao 7 do pedido): labels com
        // continuacao obrigatoria pendente (succ_fixo) NUNCA sao removidos
        // por ranking -- protecao identica ao BID Python. ----
        std::vector<int> protegidos, demais;
        for (int idx : proximo_nivel) {
            int no_lab = pool[(size_t)idx].no;
            if (data.succ_fixo.find(no_lab) != data.succ_fixo.end()) protegidos.push_back(idx);
            else demais.push_back(idx);
        }
        std::sort(demais.begin(), demais.end(), [&](int a, int b) {
            return pool[(size_t)a].rc_fechamento < pool[(size_t)b].rc_fechamento;
            });
        int slots_restantes = std::max(0, max_labels_por_no - (int)protegidos.size());
        if ((int)demais.size() > slots_restantes) demais.resize((size_t)slots_restantes);

        nivel_atual = protegidos;
        nivel_atual.insert(nivel_atual.end(), demais.begin(), demais.end());
        nivel++;
    }

    double tempo_decorrido = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_inicio).count();

    std::sort(candidatas.begin(), candidatas.end(),
        [](const CandidataMulti& a, const CandidataMulti& b) { return a.rc < b.rc; });
    if ((int)candidatas.size() > max_cand_efetivo) candidatas.resize((size_t)max_cand_efetivo);

    py::list saida;
    for (auto& c : candidatas) {
        std::vector<int> binx((size_t)nbcd, 0);
        for (int v : c.seq) if (v >= 1 && v <= nbcd) binx[(size_t)(v - 1)] = 1;
        py::dict d;
        d["k"] = k;
        d["seq"] = c.seq;
        d["binx"] = binx;
        d["custo"] = c.custo;
        d["rc"] = c.rc;
        d["origem"] = std::string("BID_SILVA_CPP");
        saida.append(d);
    }

    // BID e SEMPRE heuristico -- completa=False, nunca certifica ausencia
    // de coluna negativa (secao 2 do pedido). timeout so reflete o teto de
    // seguranca defensivo (max_total_labels/timeout_s), NAO um orcamento do
    // algoritmo em si (que no BID Python nao existe).
    return py::make_tuple(saida, false, timeout_flag, total_labels, nivel, tempo_decorrido);
}
