// vrptw_pd.cpp  (compile como .pyd via pybind11)
//
// Este arquivo implementa a versão "construtiva míope" com Progressive Widening
// igual ao seu Python SUB_PROG_DIN_PW:
//
// - Para cada B em widening_seq (ex: [1,2,4,8,-1] onde -1=ALL):
//   tenta construir uma rota via DFS:
//     * em cada nó i, gera candidatos viáveis
//     * ordena por delta_rc(i,j)
//     * tenta somente os Top-B (ou ALL)
//     * early-exit assim que fechar no depósito final com rc < -eps
//
// Funções exportadas:
//   - hello() -> string
//   - sub_prog_din_pw_greedy(tt,a,b,s,d,pi,sigma_k,cap_k,nbcd,dep0,depf,widening_seq,eps)
//       -> (dict, rc) ou (None,None)
//   - sub_prog_din_pw_branch_greedy(..., mu_flat, forbid_flat, req_i, req_j)
//       -> idem, mas com:
//         * mu_flat: nbn*nbn, entra como -mu(i,j) no delta_rc
//         * forbid_flat: nbn*nbn, 0/1 bloqueia arco
//         * req_i/req_j: lista de arcos "obrigatórios" (todos devem aparecer)

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <bitset>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace py = pybind11;

// ------------------ helpers ------------------

static inline std::bitset<128> cliente_mask(int c) {
    std::bitset<128> b;
    b.set(c - 1);
    return b;
}

static inline std::uint64_t arc_key(int i, int j) {
    return (std::uint64_t(std::uint32_t(i)) << 32) | std::uint32_t(j);
}

std::string hello() { return "vrptw_pd ok"; }

// ------------------ estado de DFS ------------------

struct Step {
    int node;
    double t;
    double q;
    double rc;
    std::bitset<128> mask;
};;

// ============================================================================
// GREEDY PW (base): igual ao seu SUB_PROG_DIN_PW quando você pensa nele como
// uma construtiva míope com widening.
// ============================================================================

static bool dfs_pw_greedy(
    const py::detail::unchecked_reference<double, 2>& T,
    const std::vector<double>& a,
    const std::vector<double>& b,
    const std::vector<double>& s,
    const std::vector<double>& d,
    const std::vector<double>& pi,
    double sigma_k,
    double cap_k,
    int nbcd,
    int depf,
    int B,          // -1 => ALL
    double eps,
    std::vector<int>& path,
    Step cur
) {
    int i = cur.node;

    // chegou no depósito final
    if (i == depf) {
        return (cur.rc < -eps);
    }

    struct Cand {
        int j;
        double t;
        double q;
        std::bitset<128> mask;
        double drc;
    };

    std::vector<Cand> feas;
    feas.reserve((size_t)nbcd + 1);

    auto delta_rc = [&](int ii, int jj)->double {
        double val = T(ii, jj);
        if (1 <= jj && jj <= nbcd) val -= pi[(size_t)(jj - 1)];
        if (jj == depf) val -= sigma_k;
        return val;
        };

    // clientes não visitados
    for (int c = 1; c <= nbcd; ++c) {
        auto bit = cliente_mask(c);
        if ((cur.mask & bit).any()) continue;

        auto nm = cur.mask | bit;

        double nq = cur.q + d[(size_t)c];
        if (nq > cap_k + 1e-9) continue;

        double arrive = cur.t + s[(size_t)i] + T(i, c);
        if (arrive < a[(size_t)c]) arrive = a[(size_t)c];
        if (arrive > b[(size_t)c] + 1e-9) continue;

        feas.push_back(Cand{ c, arrive, nq, nm, delta_rc(i, c) });
    }

    // depósito final (bloqueia rota vazia 0->depf)
    if (cur.mask.any()) {
        double arrive = cur.t + s[(size_t)i] + T(i, depf);
        if (arrive < a[(size_t)depf]) arrive = a[(size_t)depf];
        if (arrive <= b[(size_t)depf] + 1e-9) {
            feas.push_back(Cand{ depf, arrive, cur.q, cur.mask, delta_rc(i, depf) });
        }
    }

    if (feas.empty()) return false;

    // ordena por melhor delta_rc (exatamente sua ideia)
    std::sort(feas.begin(), feas.end(),
        [&](const Cand& x, const Cand& y) { return x.drc < y.drc; });

    int take = (B < 0) ? (int)feas.size() : std::min(B, (int)feas.size());

    for (int t = 0; t < take; ++t) {
        const auto& nx = feas[(size_t)t];

        Step nxt;
        nxt.node = nx.j;
        nxt.t = nx.t;
        nxt.q = nx.q;
        nxt.mask = nx.mask;
        nxt.rc = cur.rc + nx.drc;

        path.push_back(nx.j);

        // early-exit: fechou e rc negativo -> retorna já
        if (nx.j == depf && nxt.rc < -eps) return true;

        if (dfs_pw_greedy(T, a, b, s, d, pi, sigma_k, cap_k, nbcd, depf, B, eps, path, nxt))
            return true;

        path.pop_back();
    }

    return false;
}

py::tuple sub_prog_din_pw_greedy(
    py::array_t<double, py::array::c_style | py::array::forcecast> tt, // nbn x nbn
    std::vector<double> a,
    std::vector<double> b,
    std::vector<double> s,
    std::vector<double> d,
    std::vector<double> pi,        // nbcd
    double sigma_k,
    double cap_k,
    int nbcd,
    int dep0,
    int depf,
    std::vector<int> widening_seq, // ex: {1,2,4,8,-1} (-1=ALL)
    double eps
) {
    if (tt.ndim() != 2) throw std::runtime_error("tt must be 2D (nbn x nbn)");
    auto T = tt.unchecked<2>();
    int nbn = (int)T.shape(0);
    if ((int)T.shape(1) != nbn) throw std::runtime_error("tt must be square");

    if ((int)a.size() != nbn || (int)b.size() != nbn || (int)s.size() != nbn || (int)d.size() != nbn)
        throw std::runtime_error("a,b,s,d must have size nbn");
    if ((int)pi.size() != nbcd)
        throw std::runtime_error("pi must have size nbcd");


    // tenta B=1, depois 2, depois 4, etc
    for (int B : widening_seq) {
        std::vector<int> path;
        path.reserve((size_t)nbcd + 2);
        path.push_back(dep0);

        Step start;
        start.node = dep0;
        start.t = std::max(a[(size_t)dep0], 0.0);
        start.q = 0.0;
        start.rc = 0.0;
        start.mask.reset();

        bool ok = dfs_pw_greedy(T, a, b, s, d, pi, sigma_k, cap_k, nbcd, depf, B, eps, path, start);
        if (!ok) continue;

        // custo real (sem duais): soma de T
        double custo_real = 0.0;
        for (int i = 0; i + 1 < (int)path.size(); ++i) custo_real += T(path[(size_t)i], path[(size_t)i + 1]);

        // custo reduzido: soma de delta_rc
        auto delta_rc = [&](int ii, int jj)->double {
            double val = T(ii, jj);
            if (1 <= jj && jj <= nbcd) val -= pi[(size_t)(jj - 1)];
            if (jj == depf) val -= sigma_k;
            return val;
            };
        double rc = 0.0;
        for (int i = 0; i + 1 < (int)path.size(); ++i) rc += delta_rc(path[(size_t)i], path[(size_t)i + 1]);

        std::vector<int> bin((size_t)nbcd, 0);
        for (int v : path) if (1 <= v && v <= nbcd) bin[(size_t)(v - 1)] = 1;

        py::dict out;
        out["clientes"] = path;
        out["custo"] = custo_real;
        out["bin_xij"] = bin;

        return py::make_tuple(out, rc);
    }

    return py::make_tuple(py::none(), py::none());
}

// ============================================================================
// GREEDY PW (branch): com mu_flat, forbid_flat e arcos obrigatórios (req_i/req_j)
// ============================================================================

static bool dfs_pw_branch_greedy(
    const py::detail::unchecked_reference<double, 2>& T,
    const std::vector<double>& a,
    const std::vector<double>& b,
    const std::vector<double>& s,
    const std::vector<double>& d,
    const std::vector<double>& pi,
    double sigma_k,
    double cap_k,
    int nbcd,
    int depf,
    int B,              // -1 => ALL
    double eps,
    const std::vector<double>& mu_flat,      // nbn*nbn
    const std::vector<std::uint8_t>& forbid, // nbn*nbn (0/1) ou vazio
    const std::unordered_map<std::uint64_t, int>& req_map,
    std::uint32_t full_req_mask,
    std::vector<int>& path,
    Step cur,
    std::uint32_t req_mask
) {
    int nbn = (int)T.shape(0);
    int i = cur.node;

    if (i == depf) {
        return (req_mask == full_req_mask) && (cur.rc < -eps);
    }

    auto is_forbidden = [&](int ii, int jj)->bool {
        if (forbid.empty()) return false;
        return forbid[(size_t)(ii * nbn + jj)] != 0;
        };

    auto mu = [&](int ii, int jj)->double {
        return mu_flat[(size_t)(ii * nbn + jj)];
        };

    auto upd_req = [&](std::uint32_t rm, int ii, int jj)->std::uint32_t {
        if (full_req_mask == 0u) return 0u;
        auto it = req_map.find(arc_key(ii, jj));
        if (it == req_map.end()) return rm;
        return rm | (1u << (unsigned)it->second);
        };

    struct Cand {
        int j;
        double t;
        double q;
        std::bitset<128> mask;
        std::uint32_t rmask;
        double drc;
    };

    std::vector<Cand> feas;
    feas.reserve((size_t)nbcd + 1);

    auto delta_rc = [&](int ii, int jj)->double {
        double val = T(ii, jj);
        val -= mu(ii, jj);
        if (1 <= jj && jj <= nbcd) val -= pi[(size_t)(jj - 1)];
        if (jj == depf) val -= sigma_k;
        return val;
        };

    // clientes
    for (int c = 1; c <= nbcd; ++c) {
        if (is_forbidden(i, c)) continue;

        auto bit = cliente_mask(c);
        if ((cur.mask & bit).any()) continue;
        auto nm = cur.mask | bit;

        std::uint32_t nrm = upd_req(req_mask, i, c);

        double nq = cur.q + d[(size_t)c];
        if (nq > cap_k + 1e-9) continue;

        double arrive = cur.t + s[(size_t)i] + T(i, c);
        if (arrive < a[(size_t)c]) arrive = a[(size_t)c];
        if (arrive > b[(size_t)c] + 1e-9) continue;

        feas.push_back(Cand{ c, arrive, nq, nm, nrm, delta_rc(i, c) });
    }

    // depf: só deixa fechar se req completo e não vazia
    if (cur.mask.any() && !is_forbidden(i, depf)) {
        std::uint32_t nrm = upd_req(req_mask, i, depf);
        if (nrm == full_req_mask) {
            double arrive = cur.t + s[(size_t)i] + T(i, depf);
            if (arrive < a[(size_t)depf]) arrive = a[(size_t)depf];
            if (arrive <= b[(size_t)depf] + 1e-9) {
                feas.push_back(Cand{ depf, arrive, cur.q, cur.mask, nrm, delta_rc(i, depf) });
            }
        }
    }

    if (feas.empty()) return false;

    std::sort(feas.begin(), feas.end(),
        [&](const Cand& x, const Cand& y) { return x.drc < y.drc; });

    int take = (B < 0) ? (int)feas.size() : std::min(B, (int)feas.size());

    for (int t = 0; t < take; ++t) {
        const auto& nx = feas[(size_t)t];

        Step nxt;
        nxt.node = nx.j;
        nxt.t = nx.t;
        nxt.q = nx.q;
        nxt.mask = nx.mask;
        nxt.rc = cur.rc + nx.drc;

        path.push_back(nx.j);

        if (nx.j == depf && nx.rmask == full_req_mask && nxt.rc < -eps) return true;

        if (dfs_pw_branch_greedy(T, a, b, s, d, pi, sigma_k, cap_k, nbcd, depf, B, eps,
            mu_flat, forbid, req_map, full_req_mask,
            path, nxt, nx.rmask))
            return true;

        path.pop_back();
    }

    return false;
}

py::tuple sub_prog_din_pw_branch_greedy(
    py::array_t<double, py::array::c_style | py::array::forcecast> tt,
    std::vector<double> a,
    std::vector<double> b,
    std::vector<double> s,
    std::vector<double> d,
    std::vector<double> pi,
    double sigma_k,
    double cap_k,
    int nbcd,
    int dep0,
    int depf,
    std::vector<int> widening_seq,
    double eps,
    std::vector<double> mu_flat,             // nbn*nbn
    std::vector<std::uint8_t> forbid_flat,   // nbn*nbn ou vazio
    std::vector<int> req_i,
    std::vector<int> req_j
) {
    if (tt.ndim() != 2) throw std::runtime_error("tt must be 2D (nbn x nbn)");
    auto T = tt.unchecked<2>();
    int nbn = (int)T.shape(0);
    if ((int)T.shape(1) != nbn) throw std::runtime_error("tt must be square");

    if ((int)a.size() != nbn || (int)b.size() != nbn || (int)s.size() != nbn || (int)d.size() != nbn)
        throw std::runtime_error("a,b,s,d must have size nbn");
    if ((int)pi.size() != nbcd)
        throw std::runtime_error("pi must have size nbcd");
    if ((int)mu_flat.size() != nbn * nbn)
        throw std::runtime_error("mu_flat must have size nbn*nbn");
    if (!forbid_flat.empty() && (int)forbid_flat.size() != nbn * nbn)
        throw std::runtime_error("forbid_flat must have size nbn*nbn (or be empty)");
    if (req_i.size() != req_j.size())
        throw std::runtime_error("req_i and req_j must have same length");

    int m = (int)req_i.size();
    if (m > 31) throw std::runtime_error("too many required arcs (max 31) for uint32 req_mask");

    std::unordered_map<std::uint64_t, int> req_map;
    req_map.reserve((size_t)m * 2 + 8);
    for (int t = 0; t < m; ++t) req_map[arc_key(req_i[(size_t)t], req_j[(size_t)t])] = t;
    std::uint32_t full_req_mask = (m == 0) ? 0u : (std::uint32_t)((1u << m) - 1u);

    for (int B : widening_seq) {
        std::vector<int> path;
        path.reserve((size_t)nbcd + 2);
        path.push_back(dep0);

        Step start;
        start.node = dep0;
        start.t = std::max(a[(size_t)dep0], 0.0);
        start.q = 0.0;
        start.rc = 0.0;
        start.mask.reset();

        bool ok = dfs_pw_branch_greedy(T, a, b, s, d, pi, sigma_k, cap_k, nbcd, depf, B, eps,
            mu_flat, forbid_flat, req_map, full_req_mask,
            path, start, 0u);
        if (!ok) continue;

        // custo real
        double custo_real = 0.0;
        for (int i = 0; i + 1 < (int)path.size(); ++i) custo_real += T(path[(size_t)i], path[(size_t)i + 1]);

        // custo reduzido
        auto delta_rc = [&](int ii, int jj)->double {
            double val = T(ii, jj);
            val -= mu_flat[(size_t)(ii * nbn + jj)];
            if (1 <= jj && jj <= nbcd) val -= pi[(size_t)(jj - 1)];
            if (jj == depf) val -= sigma_k;
            return val;
            };
        double rc = 0.0;
        for (int i = 0; i + 1 < (int)path.size(); ++i) rc += delta_rc(path[(size_t)i], path[(size_t)i + 1]);

        std::vector<int> bin((size_t)nbcd, 0);
        for (int v : path) if (1 <= v && v <= nbcd) bin[(size_t)(v - 1)] = 1;

        py::dict out;
        out["clientes"] = path;
        out["custo"] = custo_real;
        out["bin_xij"] = bin;

        return py::make_tuple(out, rc);
    }

    return py::make_tuple(py::none(), py::none());
}

// ------------------ module ------------------

// ===================== BIDIRECIONAL =====================
#include <deque>
#include <unordered_set>

struct BiLabelF {
    int no;
    double tempo;
    double carga;
    double custo_mod;
    std::bitset<128> mask;
    int pai;
    bool ativo;
    int nvisit;
};

struct BiLabelB {
    int no;
    double tempo_back;
    double carga;
    double custo_mod;
    std::bitset<128> mask;
    int pai;
    bool ativo;
    int nvisit;
};



static inline bool domina_bi(double cA, double tA, double qA,
    double cB, double tB, double qB,
    double tol = 1e-6) {
    return (
        cA <= cB + tol &&
        tA <= tB + tol &&
        qA <= qB + tol &&
        (cA < cB - tol || tA < tB - tol || qA < qB - tol)
        );
}

static std::vector<int> rota_forward_cpp(const std::vector<BiLabelF>& rot, int idx) {
    std::vector<int> seq;
    while (idx != -1) {
        seq.push_back(rot[(size_t)idx].no);
        idx = rot[(size_t)idx].pai;
    }
    std::reverse(seq.begin(), seq.end());
    return seq;
}

static std::vector<int> rota_backward_cpp(const std::vector<BiLabelB>& rot, int idx) {
    std::vector<int> seq;
    while (idx != -1) {
        seq.push_back(rot[(size_t)idx].no);
        idx = rot[(size_t)idx].pai;
    }
    return seq;
}

struct NodeMaskKey {
    int no;
    std::bitset<128> mask;

    bool operator==(const NodeMaskKey& other) const {
        return no == other.no && mask == other.mask;
    }
};

struct NodeMaskKeyHash {
    std::size_t operator()(const NodeMaskKey& k) const {
        std::size_t h1 = std::hash<int>{}(k.no);
        std::size_t h2 = std::hash<std::string>{}(k.mask.to_string());
        return h1 ^ (h2 << 1);
    }
};

py::tuple sub_prog_din_bidirecional(
    py::array_t<double, py::array::c_style | py::array::forcecast> tt,   // nbn x nbn
    std::vector<double> a,
    std::vector<double> b,
    std::vector<double> s,
    std::vector<double> d,
    std::vector<double> pi,           // nbcd
    double sigma_k,
    double cap_k,
    int nbcd,
    int dep0,
    int depf,
    std::vector<double> mu_flat,              // nbn*nbn
    std::vector<std::uint8_t> forbid_flat,    // nbn*nbn
    std::vector<std::uint8_t> tabu_flat,      // nbn*nbn
    std::vector<int> req_i,
    std::vector<int> req_j,
    int max_labels_por_no = 100,
    int max_depth = -1,
    double eps = 1e-6
) {
    if (tt.ndim() != 2) throw std::runtime_error("tt must be 2D");
    auto T = tt.unchecked<2>();
    int nbn = (int)T.shape(0);
    if ((int)T.shape(1) != nbn) throw std::runtime_error("tt must be square");

    if ((int)a.size() != nbn || (int)b.size() != nbn || (int)s.size() != nbn || (int)d.size() != nbn)
        throw std::runtime_error("a,b,s,d must have size nbn");
    if ((int)pi.size() != nbcd)
        throw std::runtime_error("pi must have size nbcd");
    if (!mu_flat.empty() && (int)mu_flat.size() != nbn * nbn)
        throw std::runtime_error("mu_flat must have size nbn*nbn");
    if (!forbid_flat.empty() && (int)forbid_flat.size() != nbn * nbn)
        throw std::runtime_error("forbid_flat must have size nbn*nbn");
    if (!tabu_flat.empty() && (int)tabu_flat.size() != nbn * nbn)
        throw std::runtime_error("tabu_flat must have size nbn*nbn");
    if ((int)req_i.size() != (int)req_j.size())
        throw std::runtime_error("req_i and req_j must have same length");


    if (max_depth < 0) {
        max_depth = (nbcd + 1) / 2;
    }

    if (mu_flat.empty()) mu_flat.assign((size_t)nbn * (size_t)nbn, 0.0);
    if (forbid_flat.empty()) forbid_flat.assign((size_t)nbn * (size_t)nbn, 0);
    if (tabu_flat.empty()) tabu_flat.assign((size_t)nbn * (size_t)nbn, 0);

    std::unordered_set<std::uint64_t> fixados_k;
    fixados_k.reserve(req_i.size() * 2 + 1);
    std::unordered_map<int, int> succ_fixo;
    std::unordered_map<int, int> pred_fixo;

    for (size_t t = 0; t < req_i.size(); ++t) {
        int i = req_i[t];
        int j = req_j[t];
        auto  key = arc_key(i, j);
        fixados_k.insert(key);

        auto its = succ_fixo.find(i);
        if (its != succ_fixo.end() && its->second != j) {
            return py::make_tuple(py::none(), py::none());
        }
        auto itp = pred_fixo.find(j);
        if (itp != pred_fixo.end() && itp->second != i) {
            return py::make_tuple(py::none(), py::none());
        }
        succ_fixo[i] = j;
        pred_fixo[j] = i;
    }

    auto idx2 = [&](int i, int j) -> size_t {
        return (size_t)i * (size_t)nbn + (size_t)j;
        };

    auto arco_proibido = [&](int i, int j) -> bool {
        return forbid_flat[idx2(i, j)] != 0;
        };

    auto arco_permitido = [&](int i, int j) -> bool {
        if (forbid_flat[idx2(i, j)] != 0) return false;
        auto its = succ_fixo.find(i);
        if (its != succ_fixo.end() && its->second != j) return false;
        auto itp = pred_fixo.find(j);
        if (itp != pred_fixo.end() && itp->second != i) return false;
        return true;
        };

    auto tabu_arc = [&](int i, int j) -> bool {
        return tabu_flat[idx2(i, j)] != 0;
        };

    auto mu = [&](int i, int j) -> double {
        return mu_flat[idx2(i, j)];
        };

    auto delta_rc = [&](int i, int j) -> double {
        double val = T(i, j) - mu(i, j);
        if (1 <= j && j <= nbcd) val -= pi[(size_t)(j - 1)];
        if (j == depf) val -= sigma_k;
        return val;
        };

    auto todos_fixados_na_rota = [&](const std::vector<int>& rota) -> bool {
        std::unordered_set<std::uint64_t> aset;
        aset.reserve(rota.size() * 2 + 1);
        for (int t = 0; t + 1 < (int)rota.size(); ++t) {
            aset.insert(arc_key(rota[(size_t)t], rota[(size_t)t + 1]));
        }
        for (const auto& kk : fixados_k) {
            if (aset.find(kk) == aset.end()) return false;
        }
        return true;
        };

    auto avaliar_rota = [&](const std::vector<int>& rota) -> py::tuple {
        if (rota.empty()) return py::make_tuple(py::none(), py::none());
        if (rota.front() != dep0 || rota.back() != depf) return py::make_tuple(py::none(), py::none());

        std::unordered_set<int> visitados;
        double tempo = std::max(a[(size_t)dep0], 0.0);
        double carga = 0.0;
        double custo_real = 0.0;
        double custo_red = 0.0;

        for (int t = 0; t + 1 < (int)rota.size(); ++t) {
            int i = rota[(size_t)t];
            int j = rota[(size_t)t + 1];

            if (i == j) return py::make_tuple(py::none(), py::none());
            if (!arco_permitido(i, j)) return py::make_tuple(py::none(), py::none());
            if (tabu_arc(i, j)) return py::make_tuple(py::none(), py::none());

            tempo = tempo + s[(size_t)i] + T(i, j);
            if (tempo < a[(size_t)j]) tempo = a[(size_t)j];
            if (tempo > b[(size_t)j] + 1e-9) return py::make_tuple(py::none(), py::none());

            if (1 <= j && j <= nbcd) {
                if (visitados.find(j) != visitados.end()) return py::make_tuple(py::none(), py::none());
                visitados.insert(j);
                carga += d[(size_t)j];
                if (carga > cap_k + 1e-9) return py::make_tuple(py::none(), py::none());
            }

            custo_real += T(i, j);
            custo_red += delta_rc(i, j);
        }

        if (visitados.empty()) return py::make_tuple(py::none(), py::none());
        if (!fixados_k.empty() && !todos_fixados_na_rota(rota)) return py::make_tuple(py::none(), py::none());

        std::vector<int> bin_xij((size_t)nbcd, 0);
        for (int v : visitados) bin_xij[(size_t)(v - 1)] = 1;

        py::dict out;
        out["clientes"] = rota;
        out["custo"] = custo_real;
        out["bin_xij"] = bin_xij;
        return py::make_tuple(out, custo_red);
        };

    // =========================
    // GERAÇÃO FORWARD
    // =========================
    std::vector<BiLabelF> rot_f;
    std::deque<int> abertos_f;
    std::unordered_map<int, std::vector<int>> labels_f_por_no;
    std::unordered_map<NodeMaskKey, std::vector<int>, NodeMaskKeyHash> fronteira_f;

    rot_f.push_back(BiLabelF{
    dep0,
    std::max(a[(size_t)dep0], 0.0),
    0.0,
    0.0,
    std::bitset<128>(),
    -1,
    true,
    0
        });

    abertos_f.push_back(0);
    labels_f_por_no[dep0].push_back(0);
    fronteira_f[{dep0, std::bitset<128>()}].push_back(0);

    while (!abertos_f.empty()) {
        int idx_atual = abertos_f.front();
        abertos_f.pop_front();
        BiLabelF& r = rot_f[(size_t)idx_atual];

        if (!r.ativo) continue;

        int no_i = r.no;
        double tempo_i = r.tempo;
        double carga_i = r.carga;
        double custo_i = r.custo_mod;
        auto  mask_i = r.mask;
        int nvisit_i = r.nvisit;

        if (nvisit_i >= max_depth) continue;

        struct CandF {
            int j;
            double tempo;
            double carga;
            std::bitset<128> mask;
        };

        std::vector<CandF> viaveis;
        viaveis.reserve((size_t)nbcd);

        for (int j = 1; j <= nbcd; ++j) {
            if ((mask_i & cliente_mask(j)).any()) continue;
            if (arco_proibido(no_i, j)) continue;
            if (!arco_permitido(no_i, j)) continue;
            if (tabu_arc(no_i, j)) continue;

            auto bit = cliente_mask(j);
            auto  nova_mask = mask_i | bit;

            double nova_carga = carga_i + d[(size_t)j];
            if (nova_carga > cap_k + 1e-9) continue;

            double tempo_chegada = tempo_i + s[(size_t)no_i] + T(no_i, j);
            if (tempo_chegada < a[(size_t)j]) tempo_chegada = a[(size_t)j];
            if (tempo_chegada > b[(size_t)j] + 1e-9) continue;

            viaveis.push_back(CandF{ j, tempo_chegada, nova_carga, nova_mask });
        }

        std::sort(viaveis.begin(), viaveis.end(),
            [&](const CandF& x, const CandF& y) {
                return delta_rc(no_i, x.j) < delta_rc(no_i, y.j);
            });

        for (const auto& cand : viaveis) {
            int j = cand.j;
            double tempo_chegada = cand.tempo;
            double nova_carga = cand.carga;
            auto  nova_mask = cand.mask;

            double custo_novo = custo_i + delta_rc(no_i, j);
            NodeMaskKey chave{ j, nova_mask };
            auto& lista = fronteira_f[chave];

            bool dominado = false;
            for (int idx_old : lista) {
                const auto& ro = rot_f[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_bi(ro.custo_mod, ro.tempo, ro.carga,
                    custo_novo, tempo_chegada, nova_carga)) {
                    dominado = true;
                    break;
                }
            }
            if (dominado) continue;

            std::vector<int> nova_lista;
            nova_lista.reserve(lista.size() + 1);
            for (int idx_old : lista) {
                auto& ro = rot_f[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_bi(custo_novo, tempo_chegada, nova_carga,
                    ro.custo_mod, ro.tempo, ro.carga)) {
                    ro.ativo = false;
                }
                else {
                    nova_lista.push_back(idx_old);
                }
            }

            int idx_novo = (int)rot_f.size();
            rot_f.push_back(BiLabelF{
                j, tempo_chegada, nova_carga, custo_novo, nova_mask,
                idx_atual, true, nvisit_i + 1
                });
            abertos_f.push_back(idx_novo);
            labels_f_por_no[j].push_back(idx_novo);
            nova_lista.push_back(idx_novo);
            lista = std::move(nova_lista);
        }

        auto& lista_no_all = labels_f_por_no[no_i];
        std::vector<int> lista_no;
        for (int idx : lista_no_all) {
            if (rot_f[(size_t)idx].ativo) lista_no.push_back(idx);
        }
        if ((int)lista_no.size() > max_labels_por_no) {
            std::sort(lista_no.begin(), lista_no.end(),
                [&](int ia, int ib) {
                    const auto& A = rot_f[(size_t)ia];
                    const auto& B = rot_f[(size_t)ib];
                    if (A.custo_mod != B.custo_mod) return A.custo_mod < B.custo_mod;
                    if (A.tempo != B.tempo) return A.tempo < B.tempo;
                    return A.carga < B.carga;
                });
            std::unordered_set<int> manter;
            for (int z = 0; z < max_labels_por_no; ++z) manter.insert(lista_no[(size_t)z]);
            for (int z = max_labels_por_no; z < (int)lista_no.size(); ++z) {
                rot_f[(size_t)lista_no[(size_t)z]].ativo = false;
            }
            std::vector<int> filtrada;
            for (int idx : lista_no_all) {
                if (manter.find(idx) != manter.end()) filtrada.push_back(idx);
            }
            lista_no_all = std::move(filtrada);
        }
    }

    // =========================
    // GERAÇÃO BACKWARD
    // =========================
    std::vector<BiLabelB> rot_b;
    std::deque<int> abertos_b;
    std::unordered_map<int, std::vector<int>> labels_b_por_no;
    std::unordered_map<NodeMaskKey, std::vector<int>, NodeMaskKeyHash> fronteira_b;

    rot_b.push_back(BiLabelB{
        depf, 0.0, 0.0, 0.0, std::bitset<128>(), -1, true, 0
        });

    fronteira_b[{depf, std::bitset<128>()}].push_back(0);

    abertos_b.push_back(0);
    labels_b_por_no[depf].push_back(0);

    while (!abertos_b.empty()) {
        int idx_atual = abertos_b.front();
        abertos_b.pop_front();
        BiLabelB& r = rot_b[(size_t)idx_atual];

        if (!r.ativo) continue;

        int no_j = r.no;
        double tempo_back_j = r.tempo_back;
        double carga_j = r.carga;
        double custo_j = r.custo_mod;
        auto  mask_j = r.mask;
        int nvisit_j = r.nvisit;

        if (nvisit_j >= max_depth) continue;

        struct CandB {
            int i;
            double tempo_back;
            double carga;
            std::bitset<128> mask;
            double custo;
        };

        std::vector<CandB> viaveis;
        viaveis.reserve((size_t)nbcd);

        for (int i = 1; i <= nbcd; ++i) {
            
            auto bit = cliente_mask(i);
            if ((mask_j & bit).any()) continue;
            auto nova_mask = mask_j | bit;

            if (arco_proibido(i, no_j)) continue;
            if (!arco_permitido(i, no_j)) continue;
            if (tabu_arc(i, no_j)) continue;

            double nova_carga = carga_j + d[(size_t)i];
            if (nova_carga > cap_k + 1e-9) continue;

            double novo_tempo_back = tempo_back_j + s[(size_t)i] + T(i, no_j);
            double custo_novo = custo_j + delta_rc(i, no_j);

            viaveis.push_back(CandB{ i, novo_tempo_back, nova_carga, nova_mask, custo_novo });
        }

        std::sort(viaveis.begin(), viaveis.end(),
            [&](const CandB& x, const CandB& y) { return x.custo < y.custo; });

        for (const auto& cand : viaveis) {
            int i = cand.i;
            double novo_tempo_back = cand.tempo_back;
            double nova_carga = cand.carga;
            auto  nova_mask = cand.mask;
            double custo_novo = cand.custo;

            NodeMaskKey chave{ i, nova_mask };
            auto& lista = fronteira_b[chave];

            bool dominado = false;
            for (int idx_old : lista) {
                const auto& ro = rot_b[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_bi(ro.custo_mod, ro.tempo_back, ro.carga,
                    custo_novo, novo_tempo_back, nova_carga)) {
                    dominado = true;
                    break;
                }
            }
            if (dominado) continue;

            std::vector<int> nova_lista;
            nova_lista.reserve(lista.size() + 1);
            for (int idx_old : lista) {
                auto& ro = rot_b[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_bi(custo_novo, novo_tempo_back, nova_carga,
                    ro.custo_mod, ro.tempo_back, ro.carga)) {
                    ro.ativo = false;
                }
                else {
                    nova_lista.push_back(idx_old);
                }
            }

            int idx_novo = (int)rot_b.size();
            rot_b.push_back(BiLabelB{
                i, novo_tempo_back, nova_carga, custo_novo, nova_mask,
                idx_atual, true, nvisit_j + 1
                });
            abertos_b.push_back(idx_novo);
            labels_b_por_no[i].push_back(idx_novo);
            nova_lista.push_back(idx_novo);
            lista = std::move(nova_lista);
        }

        auto& lista_no_all = labels_b_por_no[no_j];
        std::vector<int> lista_no;
        for (int idx : lista_no_all) {
            if (rot_b[(size_t)idx].ativo) lista_no.push_back(idx);
        }
        if ((int)lista_no.size() > max_labels_por_no) {
            std::sort(lista_no.begin(), lista_no.end(),
                [&](int ia, int ib) {
                    const auto& A = rot_b[(size_t)ia];
                    const auto& B = rot_b[(size_t)ib];
                    if (A.custo_mod != B.custo_mod) return A.custo_mod < B.custo_mod;
                    if (A.tempo_back != B.tempo_back) return A.tempo_back < B.tempo_back;
                    return A.carga < B.carga;
                });
            std::unordered_set<int> manter;
            for (int z = 0; z < max_labels_por_no; ++z) manter.insert(lista_no[(size_t)z]);
            for (int z = max_labels_por_no; z < (int)lista_no.size(); ++z) {
                rot_b[(size_t)lista_no[(size_t)z]].ativo = false;
            }
            std::vector<int> filtrada;
            for (int idx : lista_no_all) {
                if (manter.find(idx) != manter.end()) filtrada.push_back(idx);
            }
            lista_no_all = std::move(filtrada);
        }
    }

    // =========================
    // COMBINAÇÃO
    // =========================
    py::object melhor_coluna = py::none();
    double melhor_rc = std::numeric_limits<double>::infinity();

    std::unordered_set<int> set_f, set_b;
    for (const auto& kv : labels_f_por_no) set_f.insert(kv.first);
    for (const auto& kv : labels_b_por_no) set_b.insert(kv.first);

    for (int m = 1; m <= nbcd; ++m) {
        if (set_f.find(m) == set_f.end()) continue;
        if (set_b.find(m) == set_b.end()) continue;

        std::vector<int> lista_f, lista_b;
        for (int idx : labels_f_por_no[m]) if (rot_f[(size_t)idx].ativo) lista_f.push_back(idx);
        for (int idx : labels_b_por_no[m]) if (rot_b[(size_t)idx].ativo) lista_b.push_back(idx);

        for (int idx_f : lista_f) {
            const auto& rf = rot_f[(size_t)idx_f];
            auto rota_f = rota_forward_cpp(rot_f, idx_f);

            for (int idx_b : lista_b) {
                const auto& rb = rot_b[(size_t)idx_b];
                auto rota_b = rota_backward_cpp(rot_b, idx_b);

                auto inter = rf.mask & rb.mask;
                if (inter != cliente_mask(m)) continue;

                // remove o nó de junção duplicado no backward
                if (!rota_b.empty()) {
                    rota_b.erase(rota_b.begin());
                }

                std::vector<int> rota_completa;
                rota_completa.reserve(rota_f.size() + rota_b.size());
                rota_completa.insert(rota_completa.end(), rota_f.begin(), rota_f.end());
                rota_completa.insert(rota_completa.end(), rota_b.begin(), rota_b.end());

                auto aval = avaliar_rota(rota_completa);
                py::object coluna = aval[0];
                py::object rc_obj = aval[1];
                if (coluna.is_none()) continue;

                double rc = rc_obj.cast<double>();
                if (rc < melhor_rc) {
                    melhor_rc = rc;
                    melhor_coluna = coluna;
                }
            }
        }
    }

    // =========================
    // FECHAMENTO DIRETO FORWARD
    // =========================
    for (const auto& kv : labels_f_por_no) {
        int no_i = kv.first;
        if (no_i == depf) continue;

        for (int idx : kv.second) {
            const auto& r = rot_f[(size_t)idx];
            if (!r.ativo) continue;
            if (arco_proibido(no_i, depf)) continue;
            if (!arco_permitido(no_i, depf)) continue;
            if (tabu_arc(no_i, depf)) continue;

            auto rota_f = rota_forward_cpp(rot_f, idx);
            rota_f.push_back(depf);

            auto aval = avaliar_rota(rota_f);
            py::object coluna = aval[0];
            py::object rc_obj = aval[1];
            if (coluna.is_none()) continue;

            double rc = rc_obj.cast<double>();
            if (rc < melhor_rc) {
                melhor_rc = rc;
                melhor_coluna = coluna;
            }
        }
    }

    if (!melhor_coluna.is_none() && melhor_rc < -eps) {
        return py::make_tuple(melhor_coluna, melhor_rc);
    }

    return py::make_tuple(py::none(), py::none());
}


PYBIND11_MODULE(vrptw_pd, m) {
    m.def("hello", &hello);

    m.def("sub_prog_din_bidirecional", &sub_prog_din_bidirecional,
        py::arg("tt"),
        py::arg("a"),
        py::arg("b"),
        py::arg("s"),
        py::arg("d"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("cap_k"),
        py::arg("nbcd"),
        py::arg("dep0"),
        py::arg("depf"),
        py::arg("mu_flat") = std::vector<double>{},
        py::arg("forbid_flat") = std::vector<std::uint8_t>{},
        py::arg("tabu_flat") = std::vector<std::uint8_t>{},
        py::arg("req_i") = std::vector<int>{},
        py::arg("req_j") = std::vector<int>{},
        py::arg("max_labels_por_no") = 100,
        py::arg("max_depth") = -1,
        py::arg("eps") = 1e-6
    );

    m.def("sub_prog_din_pw_greedy", &sub_prog_din_pw_greedy,
        py::arg("tt"),
        py::arg("a"),
        py::arg("b"),
        py::arg("s"),
        py::arg("d"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("cap_k"),
        py::arg("nbcd"),
        py::arg("dep0"),
        py::arg("depf"),
        py::arg("widening_seq"),
        py::arg("eps") = 1e-6
    );

    m.def("sub_prog_din_pw_branch_greedy", &sub_prog_din_pw_branch_greedy,
        py::arg("tt"),
        py::arg("a"),
        py::arg("b"),
        py::arg("s"),
        py::arg("d"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("cap_k"),
        py::arg("nbcd"),
        py::arg("dep0"),
        py::arg("depf"),
        py::arg("widening_seq"),
        py::arg("eps") = 1e-6,
        py::arg("mu_flat") = std::vector<double>{},
        py::arg("forbid_flat") = std::vector<std::uint8_t>{},
        py::arg("req_i") = std::vector<int>{},
        py::arg("req_j") = std::vector<int>{}
    );
}