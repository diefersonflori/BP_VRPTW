// ============================================================================
// PD_SILVA_CPP: pricing EXATO Silva (label-setting/DP) em C++, reproduzindo
// SUB_PROG_PD_SILVA (metodos.py) mais rapido. Referencia estrutural oficial:
// SUB_PROG_PD_SILVA (NAO alterado por esta tarefa). Fisica oficial: a mesma
// de avaliar_rota_silva2024, replicada (nao reinventada) em
// silva_pricing_core.h -- ver esse arquivo para a fisica/branching
// reutilizaveis (nucleo comum, tambem usado pela futura BID_SILVA_CPP, NAO
// implementada nesta tarefa).
//
// Estrategia de busca (SO deste arquivo, especifica de PD): forward,
// order-por-order, level-by-level (BFS por profundidade), SEM dominancia/
// beam/ranking heuristico -- exatamente como SUB_PROG_PD_SILVA (secao 11 do
// pedido: a cronologia Silva depende do conjunto FINAL da rota -- P/hB
// dependem da mascara final, nao so do prefixo -- entao dominancia
// resource-based nao foi provada segura nem no Python nem aqui). Unico
// orcamento que pode interromper a busca ANTES de esgotar as <=nbcd orders:
// max_labels e timeout_s. completa=True SOMENTE se a arvore foi esgotada.
// ============================================================================

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <vector>
#include <string>
#include <chrono>
#include <algorithm>

#include "silva_pricing_core.h"

namespace py = pybind11;

std::string hello_silva() { return "vrptw_pd_silva ok"; }

// Diagnostico (auditoria C++ x Python, NAO usado por BID/PD): avalia UMA
// sequencia fixa reutilizando EXATAMENTE data.avaliar_fechamento (mesmo
// nucleo de silva_pricing_core.h que BID_SILVA_CPP.cpp e pricing_pd_silva
// acima usam) -- nenhuma segunda implementacao da fisica. Nao recebe
// duais/branching (pi, sigma_k, mu, forbid, req_i/j) porque nao faz
// pricing, so avalia a rota `seq` como ela vem.
py::dict avaliar_rota_silva_cpp(
    int nbn, int nbcd, int dep0, int depf,
    py::array_t<double, py::array::c_style | py::array::forcecast> dist_km_arr,
    double v_low, double v_high, double th_km, double safe_positioning_time,
    std::vector<int> plataforma_id,
    std::vector<double> set_por_plataforma,
    std::vector<double> servico,
    std::vector<std::vector<double>> ready,
    std::vector<std::vector<double>> due,
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
    double cap_deck, double cap_diesel, double cap_agua,
    double AT, double max_partida, double tdl,
    double theta_k, double varphi_k, double gamma_k, double delta_k,
    double xi_usado, double alpha_fo, double eta_fo,
    std::vector<int> seq
) {
    if (dist_km_arr.ndim() != 2)
        throw std::runtime_error("dist_km_arr deve ser 2D (nbn x nbn)");
    auto Dm = dist_km_arr.unchecked<2>();
    if ((int)Dm.shape(0) != nbn || (int)Dm.shape(1) != nbn)
        throw std::runtime_error("dist_km_arr deve ser nbn x nbn");

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

    silva::EvalResult res = data.avaliar_fechamento(seq);

    py::dict d;
    d["viavel"] = res.viavel;
    d["motivo"] = res.motivo;
    d["AT"] = res.AT;
    d["B"] = res.B;
    d["P"] = res.P;
    d["R"] = res.R;
    d["F"] = res.F;
    d["F_menos_B"] = res.F - res.B;
    d["hF"] = res.hF;
    d["hB"] = res.hB;
    d["hN"] = res.hN;
    d["hDP"] = res.hDP;
    d["f1"] = res.f1;
    d["f2"] = res.f2;
    d["custo"] = res.custo;
    return d;
}

// Declarada e implementada em BID_SILVA_CPP.cpp (novo arquivo, mesmo modulo
// pybind vrptw_pd_silva) -- pricing_pd_silva acima NAO foi alterada por essa
// adicao. Sem valores default aqui de proposito: os defaults sao definidos
// so no m.def (py::arg(...) = ...) abaixo, para nao haver 2 declaracoes com
// defaults diferentes entre os arquivos.
py::tuple pricing_bid_silva(
    int nbn, int nbcd, int dep0, int depf, int k,
    py::array_t<double, py::array::c_style | py::array::forcecast> dist_km_arr,
    double v_low, double v_high, double th_km, double safe_positioning_time,
    std::vector<int> plataforma_id,
    std::vector<double> set_por_plataforma,
    std::vector<double> servico,
    std::vector<std::vector<double>> ready,
    std::vector<std::vector<double>> due,
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
    double cap_deck, double cap_diesel, double cap_agua,
    double AT, double max_partida, double tdl,
    double theta_k, double varphi_k, double gamma_k, double delta_k,
    double xi_usado, double alpha_fo, double eta_fo,
    std::vector<double> pi,
    double sigma_k,
    std::vector<double> mu_flat,
    std::vector<std::uint8_t> forbid_flat,
    std::vector<int> req_i,
    std::vector<int> req_j,
    int max_labels_por_no,
    int max_depth,
    int max_candidatas,
    double eps,
    long long max_total_labels,
    double timeout_s
);

py::tuple pricing_pd_silva(
    // ---- estrutura ----
    int nbn, int nbcd, int dep0, int depf, int k,
    // ---- navegacao ----
    py::array_t<double, py::array::c_style | py::array::forcecast> dist_km_arr, // nbn x nbn, depf ja remapeado p/ dep0
    double v_low, double v_high, double th_km, double safe_positioning_time,
    std::vector<int> plataforma_id,             // por no; -1 para dep0/depf
    std::vector<double> set_por_plataforma,     // por id de plataforma
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
    // ---- orcamento (secao 12/13 do pedido) ----
    int max_labels = 500000,
    double timeout_s = 90.0,
    int max_candidatas = 20,
    double eps = 1e-6
) {
    auto t_inicio = std::chrono::steady_clock::now();

    if (dist_km_arr.ndim() != 2)
        throw std::runtime_error("dist_km_arr deve ser 2D (nbn x nbn)");
    auto Dm = dist_km_arr.unchecked<2>();
    if ((int)Dm.shape(0) != nbn || (int)Dm.shape(1) != nbn)
        throw std::runtime_error("dist_km_arr deve ser nbn x nbn");

    // ---- monta o nucleo reutilizavel (silva_pricing_core.h) ----
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

    // ---- K melhores candidatas por substituicao (secao 13 do pedido -- NAO
    // repetir o bug encontrado no PD Python: manter so as PRIMEIRAS
    // descobertas). Mesma politica ja usada por sub_prog_din_petro_multi
    // neste projeto. ----
    struct CandidataMulti { std::vector<int> seq; double custo; double rc; };
    std::vector<CandidataMulti> candidatas;
    if (max_candidatas < 1) max_candidatas = 1;

    auto registra = [&](const std::vector<int>& seq_fechada, double custo, double rc) {
        if (rc >= -eps) return;
        // arco de FECHAMENTO (ultimo no -> depf): UNICO lugar onde esse arco
        // e checado contra branching (secao 9 -- "fechar != continuar": a
        // expansao do label NUNCA depende disto).
        int penult = seq_fechada[seq_fechada.size() - 2];
        if (!data.arco_permitido(penult, depf)) return;
        if (!data.contem_todos_fixados(seq_fechada)) return;

        if ((int)candidatas.size() < max_candidatas) {
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

    // ---- pool de labels (secao 4/14 do pedido: parent-index + ultimo no,
    // NAO a sequencia inteira por label) ----
    std::vector<silva::SilvaLabel> pool;
    pool.reserve((size_t)std::min(max_labels, 4000000) + 16);

    silva::SilvaLabel l0;
    l0.no = dep0; l0.pai = -1; l0.profundidade = 0;
    pool.push_back(l0);
    long long total_labels = 1;

    auto fecha_e_avalia = [&](int idx_novo) {
        // FECHAR != CONTINUAR (secao 9): esta chamada NUNCA decide se o
        // label criado em idx_novo continua vivo -- so tenta registrar uma
        // candidata. O label ja foi (ou sera) anexado ao proximo nivel
        // independente do resultado aqui.
        std::vector<int> seq_fechada = silva::reconstruir_sequencia(pool, idx_novo);
        seq_fechada.push_back(depf);
        auto res = data.avaliar_fechamento(seq_fechada);
        if (!res.viavel) return;
        double rc = rc_de(res.custo, seq_fechada);
        registra(seq_fechada, res.custo, rc);
        };

    fecha_e_avalia(0);

    std::vector<int> nivel_atual = { 0 };
    int nivel = 0;
    bool limite_atingido = false;
    bool timeout_flag = false;

    auto orcamento_esgotado = [&]() -> bool {
        if (total_labels >= (long long)max_labels) return true;
        double decorrido = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_inicio).count();
        if (decorrido > timeout_s) { timeout_flag = true; return true; }
        return false;
        };

    while (nivel < nbcd && !nivel_atual.empty() && !limite_atingido) {
        std::vector<int> proximo_nivel;
        proximo_nivel.reserve(nivel_atual.size() * 4);

        for (int lab_idx : nivel_atual) {
            if (orcamento_esgotado()) { limite_atingido = true; break; }

            // copia pequena (nao a sequencia) -- pool pode realocar durante
            // a expansao, entao nao guardamos referencia.
            silva::SilvaLabel lab = pool[(size_t)lab_idx];
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

                silva::SilvaLabel novo;
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

                // secao 9: tentativa de fechar, NUNCA um criterio de poda do label.
                fecha_e_avalia(idx_novo);

                proximo_nivel.push_back(idx_novo);
            }
            if (limite_atingido) break;
        }

        nivel_atual = std::move(proximo_nivel);
        nivel++;
    }

    bool completa = !limite_atingido;
    double tempo_decorrido = std::chrono::duration<double>(std::chrono::steady_clock::now() - t_inicio).count();

    std::sort(candidatas.begin(), candidatas.end(),
        [](const CandidataMulti& a, const CandidataMulti& b) { return a.rc < b.rc; });

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
        d["origem"] = std::string("PD_SILVA_CPP");
        saida.append(d);
    }

    return py::make_tuple(saida, completa, timeout_flag, total_labels, nivel, tempo_decorrido);
}

PYBIND11_MODULE(vrptw_pd_silva, m) {
    m.def("hello_silva", &hello_silva);

    // Diagnostico (auditoria C++ x Python, secao 3): avalia UMA sequencia
    // fixa via o MESMO nucleo (SilvaPricingData::avaliar_fechamento) usado
    // por pricing_pd_silva/pricing_bid_silva abaixo. NAO faz pricing.
    m.def("avaliar_rota_silva_cpp", &avaliar_rota_silva_cpp,
        py::arg("nbn"), py::arg("nbcd"), py::arg("dep0"), py::arg("depf"),
        py::arg("dist_km_arr"),
        py::arg("v_low"), py::arg("v_high"), py::arg("th_km"), py::arg("safe_positioning_time"),
        py::arg("plataforma_id"),
        py::arg("set_por_plataforma"),
        py::arg("servico"),
        py::arg("ready"),
        py::arg("due"),
        py::arg("deck_load"),
        py::arg("deck_backload"),
        py::arg("diesel_dem"),
        py::arg("agua_dem"),
        py::arg("tempo_carreg_deck"),
        py::arg("tempo_carreg_diesel"),
        py::arg("tempo_carreg_agua"),
        py::arg("tempo_descarreg_backload"),
        py::arg("is_backload"),
        py::arg("order_due_time"),
        py::arg("has_due_time"),
        py::arg("cap_deck"), py::arg("cap_diesel"), py::arg("cap_agua"),
        py::arg("AT"), py::arg("max_partida"), py::arg("tdl"),
        py::arg("theta_k"), py::arg("varphi_k"), py::arg("gamma_k"), py::arg("delta_k"),
        py::arg("xi_usado"), py::arg("alpha_fo"), py::arg("eta_fo"),
        py::arg("seq")
    );

    m.def("pricing_pd_silva", &pricing_pd_silva,
        py::arg("nbn"), py::arg("nbcd"), py::arg("dep0"), py::arg("depf"), py::arg("k"),
        py::arg("dist_km_arr"),
        py::arg("v_low"), py::arg("v_high"), py::arg("th_km"), py::arg("safe_positioning_time"),
        py::arg("plataforma_id"),
        py::arg("set_por_plataforma"),
        py::arg("servico"),
        py::arg("ready"),
        py::arg("due"),
        py::arg("deck_load"),
        py::arg("deck_backload"),
        py::arg("diesel_dem"),
        py::arg("agua_dem"),
        py::arg("tempo_carreg_deck"),
        py::arg("tempo_carreg_diesel"),
        py::arg("tempo_carreg_agua"),
        py::arg("tempo_descarreg_backload"),
        py::arg("is_backload"),
        py::arg("order_due_time"),
        py::arg("has_due_time"),
        py::arg("cap_deck"), py::arg("cap_diesel"), py::arg("cap_agua"),
        py::arg("AT"), py::arg("max_partida"), py::arg("tdl"),
        py::arg("theta_k"), py::arg("varphi_k"), py::arg("gamma_k"), py::arg("delta_k"),
        py::arg("xi_usado"), py::arg("alpha_fo"), py::arg("eta_fo"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("mu_flat") = std::vector<double>{},
        py::arg("forbid_flat") = std::vector<std::uint8_t>{},
        py::arg("req_i") = std::vector<int>{},
        py::arg("req_j") = std::vector<int>{},
        py::arg("max_labels") = 500000,
        py::arg("timeout_s") = 90.0,
        py::arg("max_candidatas") = 20,
        py::arg("eps") = 1e-6
    );

    // BID_SILVA_CPP (novo, heuristico -- ver BID_SILVA_CPP.cpp). Mesmo
    // modulo vrptw_pd_silva, funcao separada -- nao substitui/altera
    // pricing_pd_silva acima.
    m.def("pricing_bid_silva", &pricing_bid_silva,
        py::arg("nbn"), py::arg("nbcd"), py::arg("dep0"), py::arg("depf"), py::arg("k"),
        py::arg("dist_km_arr"),
        py::arg("v_low"), py::arg("v_high"), py::arg("th_km"), py::arg("safe_positioning_time"),
        py::arg("plataforma_id"),
        py::arg("set_por_plataforma"),
        py::arg("servico"),
        py::arg("ready"),
        py::arg("due"),
        py::arg("deck_load"),
        py::arg("deck_backload"),
        py::arg("diesel_dem"),
        py::arg("agua_dem"),
        py::arg("tempo_carreg_deck"),
        py::arg("tempo_carreg_diesel"),
        py::arg("tempo_carreg_agua"),
        py::arg("tempo_descarreg_backload"),
        py::arg("is_backload"),
        py::arg("order_due_time"),
        py::arg("has_due_time"),
        py::arg("cap_deck"), py::arg("cap_diesel"), py::arg("cap_agua"),
        py::arg("AT"), py::arg("max_partida"), py::arg("tdl"),
        py::arg("theta_k"), py::arg("varphi_k"), py::arg("gamma_k"), py::arg("delta_k"),
        py::arg("xi_usado"), py::arg("alpha_fo"), py::arg("eta_fo"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("mu_flat") = std::vector<double>{},
        py::arg("forbid_flat") = std::vector<std::uint8_t>{},
        py::arg("req_i") = std::vector<int>{},
        py::arg("req_j") = std::vector<int>{},
        py::arg("max_labels_por_no") = 60,
        py::arg("max_depth") = -1,
        py::arg("max_candidatas") = 20,
        py::arg("eps") = 1e-6,
        py::arg("max_total_labels") = 5000000,
        py::arg("timeout_s") = 30.0
    );
}
