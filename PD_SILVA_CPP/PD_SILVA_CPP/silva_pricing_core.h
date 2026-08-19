#pragma once
// ============================================================================
// Nucleo Silva reutilizavel (C++): dados de instancia/veiculo + fisica
// (avaliar_rota_silva2024) + branching, SEM nenhuma estrategia de busca
// embutida. Usado hoje por PD_SILVA_CPP.cpp (label-setting exaustivo, sem
// dominancia) e, numa proxima tarefa (NAO implementada aqui), por
// BID_SILVA_CPP.cpp (heuristico/beam), reaproveitando a MESMA fisica/estado
// sem duplicar formula nenhuma.
//
// A fisica replicada aqui e EXATAMENTE a de avaliar_rota_silva2024
// (metodos.py): VL/VH com threshold, SP (safe_positioning_time), SET
// (platform_setup_seg) na entrada de plataforma nova, janelas multiplas por
// no com espera, dueTime de entrega e de pickup/backload, carregamento
// pre-feito na base (P = AT + hB_saida, onde hB_saida soma sobre TODA a
// rota fechada -- nao so o prefixo), TDL, precedencia deck (coleta antes de
// entrega dentro do bloco aberto), e nao-revisita de plataforma. Nenhuma
// formula nova e inventada aqui -- so traduzida para C++.
// ============================================================================

#include <vector>
#include <bitset>
#include <cstdint>
#include <cmath>
#include <limits>
#include <algorithm>
#include <unordered_map>
#include <string>

namespace silva {

constexpr double SEG_H = 3600.0;
constexpr int MAX_ORDERS = 64;       // suficiente para instancias de validacao (14 nesta etapa)
constexpr int MAX_PLATAFORMAS = 64;

// ----------------------------------------------------------------------
// SilvaLabel: estado MINIMO de um label no label-setting, por
// (ultimo_no, mask). NAO guarda a sequencia completa (secao 4/14 do
// pedido) -- so `pai` (indice no pool global de labels) + `no`, para
// reconstrucao sob demanda (ver reconstruir_sequencia). plataforma_aberta,
// fechadas, entrega_iniciada e deck/diesel/agua sao, matematicamente,
// funcoes puras de (ultimo_no, mask) -- mantidos aqui mesmo assim so por
// performance/legibilidade (evita recalcular a cada consulta).
// ----------------------------------------------------------------------
struct SilvaLabel {
    int no = -1;
    std::bitset<MAX_ORDERS> mask;
    int plataforma_aberta = -1;              // -1 = nenhuma (ainda em dep0)
    std::bitset<MAX_PLATAFORMAS> fechadas;   // plataformas abandonadas (nao-revisita, secao 5)
    bool entrega_iniciada = false;           // precedencia deck do bloco aberto (secao 6)
    double deck = 0.0, diesel = 0.0, agua = 0.0;
    int pai = -1;                            // indice no pool (parent), NAO a sequencia inteira
    int profundidade = 0;
};

// Resultado de avaliar_fechamento (equivalente C++ de avaliar_rota_silva2024).
// viavel/custo sao os 2 campos que o pricing (BID/PD) usa; os demais campos
// (B,P,R,F,hF,hB,hN,hDP,f1,f2,motivo) sao preenchidos so para uso
// diagnostico (avaliar_rota_silva_cpp, secao 3 do pedido de auditoria) --
// BID/PD continuam olhando so viavel/custo, nao mudam de comportamento.
struct EvalResult {
    bool viavel = false;
    double custo = 0.0;
    std::string motivo;
    double AT = 0.0, B = 0.0, P = 0.0, R = 0.0, F = 0.0;
    double hF = 0.0, hB = 0.0, hN = 0.0, hDP = 0.0;
    double f1 = 0.0, f2 = 0.0;
};

// ----------------------------------------------------------------------
// SilvaPricingData: TODOS os dados fixos de instancia+veiculo k necessarios
// para (a) fisica/FO (avaliar_fechamento) e (b) branching (arco_permitido).
// Nucleo reutilizavel entre PD_SILVA_CPP e a futura BID_SILVA_CPP -- nenhuma
// logica de busca/label-expansion mora aqui.
// ----------------------------------------------------------------------
class SilvaPricingData {
public:
    int nbn = 0, nbcd = 0, dep0 = 0, depf = 0;

    // navegacao (nav_pura_seg): VL/VH com threshold, mesma formula de
    // avaliar_rota_silva2024/nav_pura_seg.
    std::vector<std::vector<double>> dist_km; // nbn x nbn, ja remapeado depf->dep0
    double v_low = 1.0, v_high = 1.0, th_km = 0.0;
    double safe_positioning_time = 0.0;

    std::vector<int> plataforma_id;          // por no; -1 para dep0/depf
    std::vector<double> set_por_plataforma;  // por id de plataforma

    std::vector<double> servico;             // por no
    std::vector<std::vector<double>> ready;  // janelas (READY_TIME) por no
    std::vector<std::vector<double>> due;    // janelas (DUE_DATE) por no

    std::vector<double> deck_load, deck_backload, diesel_dem, agua_dem;
    std::vector<double> tempo_carreg_deck, tempo_carreg_diesel, tempo_carreg_agua;
    std::vector<double> tempo_descarreg_backload;
    std::vector<std::uint8_t> is_backload;   // por no (0/1) -- commodities[i]=="deckCargoBackload"
    std::vector<double> order_due_time;      // por no (so valido se has_due_time[no]!=0)
    std::vector<std::uint8_t> has_due_time;  // por no (0/1)

    double cap_deck = std::numeric_limits<double>::infinity();
    double cap_diesel = std::numeric_limits<double>::infinity();
    double cap_agua = std::numeric_limits<double>::infinity();

    double AT = 0.0;
    double max_partida = 0.0;  // <=0 => sem limite (mesma convencao de metodo Python)
    double tdl = 0.0;          // <=0 => sem limite
    double theta_k = 0.0, varphi_k = 0.0, gamma_k = 0.0, delta_k = 0.0;
    double xi_usado = 1.0;
    double alpha_fo = 1.0, eta_fo = 1.0;

    // branching (secao 8): mesma semantica succ_fixo/pred_fixo do Python.
    std::vector<std::uint8_t> forbid_flat;   // nbn*nbn (vazio = nenhum arco proibido)
    std::unordered_map<int, int> succ_fixo;
    std::unordered_map<int, int> pred_fixo;

    inline size_t idx2(int i, int j) const { return (size_t)i * (size_t)nbn + (size_t)j; }

    bool arco_permitido(int i, int j) const {
        if (!forbid_flat.empty() && forbid_flat[idx2(i, j)] != 0) return false;
        auto its = succ_fixo.find(i);
        if (its != succ_fixo.end() && its->second != j) return false;
        auto itp = pred_fixo.find(j);
        if (itp != pred_fixo.end() && itp->second != i) return false;
        return true;
    }

    // Todos os arcos fixados (succ_fixo) precisam estar presentes, como par
    // CONSECUTIVO, na sequencia fechada -- mesmo criterio de
    // contem_todos_fixados (pricing_silva2024/SUB_PROG_PD_SILVA). Nota:
    // arco_permitido durante a expansao JA garante que, sempre que i (com
    // succ_fixo[i] definido) aparecer no meio da sequencia (i != ultimo no),
    // o proximo no visitado foi obrigatoriamente succ_fixo[i] -- este check
    // e so a confirmacao final no fechamento (mesmo padrao do Python).
    bool contem_todos_fixados(const std::vector<int>& seq_fechada) const {
        for (const auto& kv : succ_fixo) {
            int i = kv.first, j = kv.second;
            bool achou = false;
            for (size_t t = 0; t + 1 < seq_fechada.size(); ++t) {
                if (seq_fechada[t] == i && seq_fechada[t + 1] == j) { achou = true; break; }
            }
            if (!achou) return false;
        }
        return true;
    }

    double nav_pura_seg(int i, int j) const {
        int ii = (i == depf) ? dep0 : i;
        int jj = (j == depf) ? dep0 : j;
        double d = dist_km[(size_t)ii][(size_t)jj];
        if (d == 0.0) return 0.0;
        double n = (d <= th_km) ? (d / v_low) : (th_km / v_low + (d - th_km) / v_high);
        return n * SEG_H;
    }

    // MESMA regra de tempo_arco (avaliar_rota_silva2024, silva_sp_arcos_base
    // = True sempre aqui -- mesmo default usado por pricing_silva2024/
    // SUB_PROG_PD_SILVA no B&P): SET+SP so na entrada de uma plataforma NOVA
    // (inclusive vindo da base); nunca voltando para a base.
    double tempo_arco(int i, int j) const {
        double t = nav_pura_seg(i, j);
        if (j != dep0 && j != depf) {
            int pi_ = (i == dep0 || i == depf) ? -1 : plataforma_id[(size_t)i];
            int pj_ = plataforma_id[(size_t)j];
            if (pi_ != pj_) {
                t += set_por_plataforma[(size_t)pj_];
                t += safe_positioning_time;
            }
        }
        return t;
    }

    // Equivalente C++ de avaliar_rota_silva2024. seq_fechada deve comecar em
    // dep0 e terminar em depf. Nao reimplementa nenhuma formula nova: mesma
    // sequencia de checagens/formulas do Python (metodos.py), so traduzida
    // -- inclusive a escolha otima de B_k (berco), que NAO e mais B_k=AT_k
    // fixo: B_k e escolhido dentro de [delta_min, delta_max] pelo
    // coeficiente da FO (mesma regra/formula de avaliar_rota_silva2024).
    EvalResult avaliar_fechamento(const std::vector<int>& seq_fechada) const {
        EvalResult r;
        r.AT = AT / SEG_H;
        if (seq_fechada.size() < 2 || seq_fechada.front() != dep0 || seq_fechada.back() != depf) {
            r.motivo = "rota_sem_depositos";
            return r;
        }

        const double eps = 1e-6;

        double deck_total = 0.0, diesel_total = 0.0, agua_total = 0.0;
        double hB_saida = 0.0, hB_retorno = 0.0;
        for (size_t t = 1; t + 1 < seq_fechada.size(); ++t) {
            int no = seq_fechada[t];
            deck_total += deck_load[(size_t)no];
            diesel_total += diesel_dem[(size_t)no];
            agua_total += agua_dem[(size_t)no];
            hB_saida += tempo_carreg_deck[(size_t)no] + tempo_carreg_diesel[(size_t)no] + tempo_carreg_agua[(size_t)no];
            if (is_backload[(size_t)no]) hB_retorno += tempo_descarreg_backload[(size_t)no];
        }
        if (deck_total > cap_deck + eps) { r.motivo = "capacidade_deck"; return r; }
        if (std::isfinite(cap_diesel) && diesel_total > cap_diesel + eps) { r.motivo = "capacidade_diesel"; return r; }
        if (std::isfinite(cap_agua) && agua_total > cap_agua + eps) { r.motivo = "capacidade_agua"; return r; }

        // ---- cronologia-base com B=AT (mesma convencao do Python: B=AT so
        // para SIMULAR o cronograma; a escolha final de B_k acontece so
        // depois de F_k estar calculado, no bloco de TDL abaixo). ----
        double B_base = AT;
        double P_base = B_base + hB_saida;
        if (max_partida > 0.0 && std::isfinite(max_partida) && P_base > max_partida + eps) {
            r.motivo = "max_partida_excedida";
            return r;
        }

        double deck_atual = deck_total;
        if (deck_atual > cap_deck + eps) { r.motivo = "pico_deck_inicial"; return r; }

        double tempo = P_base;
        double hN = 0.0;
        double espera_total = 0.0;
        double margem_janela_min = std::numeric_limits<double>::infinity();
        for (size_t t = 0; t + 1 < seq_fechada.size(); ++t) {
            int i = seq_fechada[t], j = seq_fechada[t + 1];

            if (j == depf) {
                double t_arco = nav_pura_seg(i, j);
                hN += t_arco / SEG_H;
                double chegada = tempo + servico[(size_t)i] + t_arco;
                if (chegada < tempo - 1e-9) { r.motivo = "tempo_retrocedeu_retorno"; return r; }
                tempo = chegada;
                continue;
            }

            double t_arco = tempo_arco(i, j);
            hN += nav_pura_seg(i, j) / SEG_H;
            double chegada = tempo + servico[(size_t)i] + t_arco;
            if (chegada < tempo - 1e-9) { r.motivo = "tempo_retrocedeu"; return r; }

            double inicio_j = -1.0;
            double due_w_sel = 0.0;
            bool achou_janela = false;
            size_t nw = std::min(ready[(size_t)j].size(), due[(size_t)j].size());
            for (size_t w = 0; w < nw; ++w) {
                double candidato = std::max(chegada, ready[(size_t)j][w]);
                if (candidato + servico[(size_t)j] <= due[(size_t)j][w] + eps) {
                    inicio_j = candidato;
                    due_w_sel = due[(size_t)j][w];
                    achou_janela = true;
                    break;
                }
            }
            if (!achou_janela) { r.motivo = "janela_no"; return r; }

            double espera = inicio_j - chegada;
            espera_total += espera;
            double margem_j = due_w_sel - servico[(size_t)j] - inicio_j;
            margem_janela_min = std::min(margem_janela_min, espera_total + margem_j);

            double fim_j = inicio_j + servico[(size_t)j];
            if (has_due_time[(size_t)j] && !is_backload[(size_t)j]) {
                if (fim_j > order_due_time[(size_t)j] + eps) { r.motivo = "dueTime_delivery"; return r; }
            }

            if (deck_backload[(size_t)j] > eps || deck_load[(size_t)j] > eps) {
                double antes = deck_atual;
                double coleta = deck_backload[(size_t)j];
                double pico = antes + coleta;
                double entrega = deck_load[(size_t)j];
                double depois = pico - entrega;
                if (pico > cap_deck + eps) { r.motivo = "pico_deck"; return r; }
                if (depois < -eps) { r.motivo = "carga_negativa"; return r; }
                deck_atual = depois;
            }

            tempo = inicio_j;
        }

        double R = tempo;
        double F = R + hB_retorno;

        for (size_t t = 1; t + 1 < seq_fechada.size(); ++t) {
            int i = seq_fechada[t];
            if (is_backload[(size_t)i] && has_due_time[(size_t)i]) {
                if (F > order_due_time[(size_t)i] + eps) { r.motivo = "dueTime_pickup"; return r; }
            }
        }

        // ---- 1) intervalo factivel de atraso de B_k: [delta_min, delta_max]
        // (mesma formula de avaliar_rota_silva2024/metodos.py) ----
        double T_baseline = F - AT;  // = T_k do compacto; nao muda com B_k
        double delta_min = 0.0;
        if (tdl > 0.0 && std::isfinite(tdl)) {
            delta_min = std::max(0.0, T_baseline - tdl);
        }

        double folga_partida = std::numeric_limits<double>::infinity();
        if (max_partida > 0.0 && std::isfinite(max_partida)) {
            folga_partida = max_partida - P_base;
        }
        double delta_max = std::min({ espera_total, margem_janela_min, folga_partida });

        if (delta_min > delta_max + eps) {
            r.motivo = "tdl_violado";
            return r;
        }

        // ---- 2) escolher delta_B em [delta_min, delta_max] pelo
        // coeficiente da FO -- MESMA regra de avaliar_rota_silva2024: dentro
        // do intervalo, enquanto o atraso e absorvido pela espera, F/R/hB/hN
        // nao mudam e hDP diminui exatamente delta -- f1 varia com
        // -(delta_k-theta_k)*delta/SEG_H, f2 fica constante. Sinal de
        // d(custo)/d(delta) = -alpha_fo*(delta_k-theta_k)/SEG_H. Nao
        // hard-coda delta_k>theta_k -- le os custos do proprio veiculo.
        const double eps_custo = 1e-9;
        double delta_B;
        if (alpha_fo > 0.0 && (delta_k - theta_k) > eps_custo) {
            delta_B = delta_max;
        } else if (alpha_fo > 0.0 && (theta_k - delta_k) > eps_custo) {
            delta_B = delta_min;
        } else {
            delta_B = delta_min;
        }

        double B = AT + delta_B;
        double P = B + hB_saida;

        double hB_saida_h = hB_saida / SEG_H;
        double hB_retorno_h = hB_retorno / SEG_H;
        double hB = hB_saida_h + hB_retorno_h;
        double hDP = (R - P) / SEG_H - hN;

        double f1 = (varphi_k - theta_k) * hB + (gamma_k - theta_k) * hN + (delta_k - theta_k) * hDP;
        double T_k_h = (F - AT) / SEG_H;
        double f2 = xi_usado * T_k_h;
        double custo = alpha_fo * f1 + (1.0 - alpha_fo) * eta_fo * f2;

        r.viavel = true;
        r.motivo = "ok";
        r.custo = custo;
        r.B = B / SEG_H; r.P = P / SEG_H; r.R = R / SEG_H; r.F = F / SEG_H;
        r.hF = (B - AT) / SEG_H; r.hB = hB; r.hN = hN; r.hDP = hDP;
        r.f1 = f1; r.f2 = f2;
        return r;
    }
};

// Reconstroi a sequencia dep0..no do label idx, andando pela cadeia de
// `pai` no pool -- NUNCA armazenada inteira em cada label (secao 4/14).
inline std::vector<int> reconstruir_sequencia(const std::vector<SilvaLabel>& pool, int idx) {
    std::vector<int> seq;
    while (idx != -1) {
        seq.push_back(pool[(size_t)idx].no);
        idx = pool[(size_t)idx].pai;
    }
    std::reverse(seq.begin(), seq.end());
    return seq;
}

} // namespace silva
