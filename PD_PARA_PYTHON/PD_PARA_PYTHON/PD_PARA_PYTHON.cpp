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

// ===================== PETRO (multi-janela + 3 recursos: deck/diesel/agua) =====================
// Labeling FORWARD monodirecional (mesmo padrao do forward de sub_prog_din_bidirecional),
// com: (i) multiplas janelas de tempo disjuntas por no (aw/bw por no, semantica
// "servico COMECA dentro da janela"), (ii) tres recursos de capacidade (deck, diesel,
// agua), (iii) fechamento direto no deposito final (sem busca backward/merge).
// Espelha o Python SUB_PROG_DIN_PETRO (metodos.py), exceto:
//  - guarda a MELHOR coluna encontrada (custo reduzido minimo) em vez de retornar
//    na primeira melhoria do "early test", como o Python faz;
//  - exige >=1 cliente na rota fechada (a coluna ociosa [dep0,depf] ja existe no pool);
//  - succ_fixo/pred_fixo (a partir de req_i/req_j) sao aplicados de verdade, com o
//    mesmo mecanismo de sub_prog_din_bidirecional (no Python SUB_PROG_DIN_PETRO,
//    arcos_fixados nunca chega a popular succ_fixo/pred_fixo).

// ---------------------------------------------------------------------------
// Regras operacionais por plataforma
// ---------------------------------------------------------------------------
// Cada cliente recebe um plataforma_id inteiro. Nos da mesma plataforma devem
// ter o mesmo id. Os depositos podem usar -1.
//
// Regra aplicada:
//   1) todos os pedidos de uma plataforma devem aparecer consecutivamente;
//   2) a plataforma nao pode ser revisitada depois de abandonada;
//   3) dentro do bloco da plataforma, todo backload de deck deve ocorrer antes
//      de qualquer entrega (deck, diesel ou agua);
//   4) em um pedido que tenha coleta e entrega, a coleta ocorre primeiro.

static inline bool petro_tem_coleta(int no, const std::vector<double>& b_deck, double tol = 1e-9) {
    return no >= 0 && no < (int)b_deck.size() && b_deck[(size_t)no] > tol;
}

static inline bool petro_tem_entrega(
    int no,
    const std::vector<double>& d_deck,
    const std::vector<double>& d_diesel,
    const std::vector<double>& d_agua,
    double tol = 1e-9
) {
    return no >= 0 && no < (int)d_deck.size() &&
        (d_deck[(size_t)no] > tol || d_diesel[(size_t)no] > tol || d_agua[(size_t)no] > tol);
}

static bool petro_plataforma_no_mask(
    const std::bitset<128>& mask,
    int plataforma,
    const std::vector<int>& plataforma_id,
    int nbcd
) {
    for (int c = 1; c <= nbcd; ++c) {
        if (mask.test((size_t)(c - 1)) && plataforma_id[(size_t)c] == plataforma) return true;
    }
    return false;
}

static bool petro_entrega_na_plataforma_no_mask(
    const std::bitset<128>& mask,
    int plataforma,
    const std::vector<int>& plataforma_id,
    const std::vector<double>& d_deck,
    const std::vector<double>& d_diesel,
    const std::vector<double>& d_agua,
    int nbcd
) {
    for (int c = 1; c <= nbcd; ++c) {
        if (!mask.test((size_t)(c - 1))) continue;
        if (plataforma_id[(size_t)c] != plataforma) continue;
        if (petro_tem_entrega(c, d_deck, d_diesel, d_agua)) return true;
    }
    return false;
}

static bool petro_coleta_na_plataforma_no_mask(
    const std::bitset<128>& mask,
    int plataforma,
    const std::vector<int>& plataforma_id,
    const std::vector<double>& b_deck,
    int nbcd
) {
    for (int c = 1; c <= nbcd; ++c) {
        if (!mask.test((size_t)(c - 1))) continue;
        if (plataforma_id[(size_t)c] != plataforma) continue;
        if (petro_tem_coleta(c, b_deck)) return true;
    }
    return false;
}

static bool petro_extensao_forward_plataforma_valida(
    int no_atual,
    int candidato,
    const std::bitset<128>& mask,
    const std::vector<int>& plataforma_id,
    const std::vector<double>& d_deck,
    const std::vector<double>& b_deck,
    const std::vector<double>& d_diesel,
    const std::vector<double>& d_agua,
    int nbcd
) {
    const int p_cand = plataforma_id[(size_t)candidato];
    const int p_atual = (1 <= no_atual && no_atual <= nbcd) ? plataforma_id[(size_t)no_atual] : -1;

    // Se a plataforma do candidato ja apareceu e nao e a plataforma atual,
    // a extensao retornaria a uma plataforma ja encerrada.
    if (p_cand != p_atual && petro_plataforma_no_mask(mask, p_cand, plataforma_id, nbcd)) return false;

    // Se ja houve qualquer entrega nessa plataforma, nao pode aparecer uma
    // coleta posteriormente.
    if (petro_tem_coleta(candidato, b_deck) &&
        petro_entrega_na_plataforma_no_mask(mask, p_cand, plataforma_id, d_deck, d_diesel, d_agua, nbcd)) {
        return false;
    }

    return true;
}

static bool petro_extensao_backward_plataforma_valida(
    int candidato,
    int no_seguinte,
    const std::bitset<128>& mask_sufixo,
    const std::vector<int>& plataforma_id,
    const std::vector<double>& d_deck,
    const std::vector<double>& b_deck,
    const std::vector<double>& d_diesel,
    const std::vector<double>& d_agua,
    int nbcd
) {
    const int p_cand = plataforma_id[(size_t)candidato];
    const int p_seg = (1 <= no_seguinte && no_seguinte <= nbcd) ? plataforma_id[(size_t)no_seguinte] : -1;

    // No backward, mudar para uma plataforma que ja existe no sufixo criaria
    // dois blocos separados da mesma plataforma.
    if (p_cand != p_seg && petro_plataforma_no_mask(mask_sufixo, p_cand, plataforma_id, nbcd)) return false;

    // Ao prependermos um pedido, uma entrega nao pode ficar antes de uma coleta
    // que ja existe no sufixo da mesma plataforma.
    if (petro_tem_entrega(candidato, d_deck, d_diesel, d_agua) &&
        petro_coleta_na_plataforma_no_mask(mask_sufixo, p_cand, plataforma_id, b_deck, nbcd)) {
        return false;
    }

    return true;
}

static bool petro_ordem_plataformas_valida(
    const std::vector<int>& rota,
    const std::vector<int>& plataforma_id,
    const std::vector<double>& d_deck,
    const std::vector<double>& b_deck,
    const std::vector<double>& d_diesel,
    const std::vector<double>& d_agua,
    int nbcd
) {
    std::unordered_set<int> plataformas_encerradas;
    int plataforma_atual = -1;
    bool entrega_iniciada = false;

    for (int no : rota) {
        if (!(1 <= no && no <= nbcd)) continue;
        const int p = plataforma_id[(size_t)no];

        if (p != plataforma_atual) {
            if (plataforma_atual >= 0) plataformas_encerradas.insert(plataforma_atual);
            if (plataformas_encerradas.find(p) != plataformas_encerradas.end()) return false;
            plataforma_atual = p;
            entrega_iniciada = false;
        }

        const bool coleta = petro_tem_coleta(no, b_deck);
        const bool entrega = petro_tem_entrega(no, d_deck, d_diesel, d_agua);

        if (coleta && entrega_iniciada) return false;
        if (entrega) entrega_iniciada = true;
    }

    return true;
}

struct PetroLabel {
    int no;
    double tempo;
    double soma_d;   // soma das entregas de deck da rota ate aqui
    double net;      // net_antes acumulado (Sum b_j - d_j dos nos anteriores)
    double m;        // pico de ocupacao de deck (max de net_antes_i + b_i)
    double diesel;
    double agua;
    double custo_mod;
    std::bitset<128> mask;
    int pai;
    bool ativo;
};

// Dominancia em (custo_mod, tempo, m): para uma mesma chave (no, mask) os
// acumulados de soma_d/diesel/agua sao sempre os mesmos (somas fixas das
// demandas dos clientes do mask, independente da ordem de visita), mas o
// pico de ocupacao de deck `m` DEPENDE da ordem de visita -- por isso entra
// na dominancia como uma 3a dimensao (Pareto em custo, tempo, m).
static inline bool domina_petro(double cA, double tA, double mA, double cB, double tB, double mB, double tol = 1e-6) {
    return (
        cA <= cB + tol &&
        tA <= tB + tol &&
        mA <= mB + tol &&
        (cA < cB - tol || tA < tB - tol || mA < mB - tol)
        );
}

static std::vector<int> rota_forward_petro(const std::vector<PetroLabel>& rot, int idx) {
    std::vector<int> seq;
    while (idx != -1) {
        seq.push_back(rot[(size_t)idx].no);
        idx = rot[(size_t)idx].pai;
    }
    std::reverse(seq.begin(), seq.end());
    return seq;
}

py::tuple sub_prog_din_petro(
    py::array_t<double, py::array::c_style | py::array::forcecast> tt,   // nbn x nbn
    std::vector<std::vector<double>> aw,      // aw[i] = READY das janelas do no i (ordenadas)
    std::vector<std::vector<double>> bw,      // bw[i] = DUE das janelas do no i
    std::vector<double> s,                    // servico por no
    std::vector<double> d_deck,               // entrega de deck por no
    std::vector<double> b_deck,               // backload de deck por no
    std::vector<double> d_diesel,
    std::vector<double> d_agua,
    std::vector<int> plataforma_id,           // id da plataforma por no; depositos podem ser -1
    std::vector<double> pi,                   // nbcd
    double sigma_k,
    double cap_deck,
    double cap_diesel,
    double cap_agua,
    int nbcd,
    int dep0,
    int depf,
    std::vector<double> mu_flat,              // nbn*nbn
    std::vector<std::uint8_t> forbid_flat,    // nbn*nbn
    std::vector<int> req_i,
    std::vector<int> req_j,
    int max_labels_por_no = 200,
    double eps = 1e-6
) {
    if (tt.ndim() != 2) throw std::runtime_error("tt must be 2D (nbn x nbn)");
    auto T = tt.unchecked<2>();
    int nbn = (int)T.shape(0);
    if ((int)T.shape(1) != nbn) throw std::runtime_error("tt must be square");

    if ((int)aw.size() != nbn || (int)bw.size() != nbn)
        throw std::runtime_error("aw,bw must have size nbn");
    if ((int)s.size() != nbn || (int)d_deck.size() != nbn || (int)b_deck.size() != nbn ||
        (int)d_diesel.size() != nbn || (int)d_agua.size() != nbn)
        throw std::runtime_error("s,d_deck,b_deck,d_diesel,d_agua must have size nbn");
    if ((int)plataforma_id.size() != nbn)
        throw std::runtime_error("plataforma_id must have size nbn");
    for (int c = 1; c <= nbcd; ++c) {
        if (plataforma_id[(size_t)c] < 0)
            throw std::runtime_error("plataforma_id must be nonnegative for every client");
    }
    if ((int)pi.size() != nbcd)
        throw std::runtime_error("pi must have size nbcd");
    if (!mu_flat.empty() && (int)mu_flat.size() != nbn * nbn)
        throw std::runtime_error("mu_flat must have size nbn*nbn");
    if (!forbid_flat.empty() && (int)forbid_flat.size() != nbn * nbn)
        throw std::runtime_error("forbid_flat must have size nbn*nbn");
    if ((int)req_i.size() != (int)req_j.size())
        throw std::runtime_error("req_i and req_j must have same length");

    if (mu_flat.empty()) mu_flat.assign((size_t)nbn * (size_t)nbn, 0.0);
    if (forbid_flat.empty()) forbid_flat.assign((size_t)nbn * (size_t)nbn, 0);

    // ---- fixos (succ/pred), mesmo mecanismo do bidirecional ----
    std::unordered_map<int, int> succ_fixo;
    std::unordered_map<int, int> pred_fixo;
    for (size_t t = 0; t < req_i.size(); ++t) {
        int i = req_i[t];
        int j = req_j[t];
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

    auto arco_permitido = [&](int i, int j) -> bool {
        if (forbid_flat[idx2(i, j)] != 0) return false;
        auto its = succ_fixo.find(i);
        if (its != succ_fixo.end() && its->second != j) return false;
        auto itp = pred_fixo.find(j);
        if (itp != pred_fixo.end() && itp->second != i) return false;
        return true;
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

    // extensao multi-janela: acha a primeira janela r com
    // max(chegada, aw[j][r]) + s[j] <= bw[j][r] + EPS_WIN;
    // servico comeca em max(chegada, aw[j][r]). Sem janela viavel -> false (poda).
    const double EPS_WIN = 1e-6;
    auto extensao_janela = [&](double tempo_bruto, int j, double& tempo_saida) -> bool {
        const auto& aj = aw[(size_t)j];
        const auto& bj = bw[(size_t)j];
        double servico = s[(size_t)j];
        for (size_t r = 0; r < bj.size(); ++r) {
            double aval = (r < aj.size()) ? aj[r] : 0.0;
            double inicio = std::max(tempo_bruto, aval);
            if (inicio + servico <= bj[r] + EPS_WIN) {
                tempo_saida = inicio;
                return true;
            }
        }
        return false;
        };

    auto montar_dict = [&](const std::vector<int>& rota) -> py::dict {
        double custo_real = 0.0;
        for (size_t t = 0; t + 1 < rota.size(); ++t) custo_real += T(rota[t], rota[t + 1]);
        std::vector<int> bin_xij((size_t)nbcd, 0);
        for (int v : rota) if (1 <= v && v <= nbcd) bin_xij[(size_t)(v - 1)] = 1;
        py::dict out;
        out["clientes"] = rota;
        out["custo"] = custo_real;
        out["bin_xij"] = bin_xij;
        return out;
        };

    double tempo_inicial;
    {
        const auto& a0 = aw[(size_t)dep0];
        tempo_inicial = std::max(a0.empty() ? 0.0 : a0[0], 0.0);
    }

    std::vector<PetroLabel> rot;
    std::deque<int> abertos;
    std::unordered_map<int, std::vector<int>> labels_por_no;
    std::unordered_map<NodeMaskKey, std::vector<int>, NodeMaskKeyHash> fronteira;

    rot.push_back(PetroLabel{
        dep0, tempo_inicial, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, std::bitset<128>(), -1, true
        });
    abertos.push_back(0);
    labels_por_no[dep0].push_back(0);
    fronteira[{dep0, std::bitset<128>()}].push_back(0);

    py::object melhor_coluna = py::none();
    double melhor_rc = std::numeric_limits<double>::infinity();

    while (!abertos.empty()) {
        int idx_atual = abertos.front();
        abertos.pop_front();
        PetroLabel& r = rot[(size_t)idx_atual];
        if (!r.ativo) continue;

        int no_i = r.no;
        double tempo_i = r.tempo;
        double soma_d_i = r.soma_d;
        double net_i = r.net;
        double m_i = r.m;
        double diesel_i = r.diesel;
        double agua_i = r.agua;
        double custo_i = r.custo_mod;
        auto mask_i = r.mask;

        if (no_i == depf) {
            if (mask_i.any() && custo_i < melhor_rc) {
                melhor_rc = custo_i;
                melhor_coluna = montar_dict(rota_forward_petro(rot, idx_atual));
            }
            continue;
        }

        std::vector<int> candidatos;
        auto its0 = succ_fixo.find(no_i);
        if (its0 != succ_fixo.end()) {
            candidatos.push_back(its0->second);
        }
        else {
            candidatos.reserve((size_t)nbcd + 1);
            for (int c = 1; c <= nbcd; ++c) {
                if (!(mask_i & cliente_mask(c)).any()) candidatos.push_back(c);
            }
            candidatos.push_back(depf);
        }

        for (int j : candidatos) {
            if (!arco_permitido(no_i, j)) continue;

            std::bitset<128> nova_mask = mask_i;
            if (1 <= j && j <= nbcd) {
                auto bit = cliente_mask(j);
                if ((mask_i & bit).any()) continue;
                if (!petro_extensao_forward_plataforma_valida(
                    no_i, j, mask_i, plataforma_id, d_deck, b_deck, d_diesel, d_agua, nbcd)) continue;
                nova_mask = mask_i | bit;
            }

            double novo_soma_d = soma_d_i;
            double novo_net = net_i;
            double novo_m = m_i;
            double novo_diesel = diesel_i;
            double nova_agua = agua_i;
            if (1 <= j && j <= nbcd) {
                double pico_cand = net_i + b_deck[(size_t)j];
                novo_m = std::max(m_i, pico_cand);
                novo_net = net_i + b_deck[(size_t)j] - d_deck[(size_t)j];
                novo_soma_d = soma_d_i + d_deck[(size_t)j];
                novo_diesel += d_diesel[(size_t)j];
                nova_agua += d_agua[(size_t)j];
            }
            if (novo_soma_d + novo_m > cap_deck + 1e-9) continue;
            if (novo_diesel > cap_diesel + 1e-9) continue;
            if (nova_agua > cap_agua + 1e-9) continue;

            double tempo_bruto = tempo_i + s[(size_t)no_i] + T(no_i, j);
            double tempo_chegada;
            if (!extensao_janela(tempo_bruto, j, tempo_chegada)) continue;

            double custo_novo = custo_i + delta_rc(no_i, j);

            NodeMaskKey chave{ j, nova_mask };
            auto& lista = fronteira[chave];

            bool dominado = false;
            for (int idx_old : lista) {
                const auto& ro = rot[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_petro(ro.custo_mod, ro.tempo, ro.m, custo_novo, tempo_chegada, novo_m)) {
                    dominado = true;
                    break;
                }
            }
            if (dominado) continue;

            std::vector<int> nova_lista;
            nova_lista.reserve(lista.size() + 1);
            for (int idx_old : lista) {
                auto& ro = rot[(size_t)idx_old];
                if (!ro.ativo) continue;
                if (domina_petro(custo_novo, tempo_chegada, novo_m, ro.custo_mod, ro.tempo, ro.m)) {
                    ro.ativo = false;
                }
                else {
                    nova_lista.push_back(idx_old);
                }
            }

            int idx_novo = (int)rot.size();
            rot.push_back(PetroLabel{
                j, tempo_chegada, novo_soma_d, novo_net, novo_m, novo_diesel, nova_agua, custo_novo,
                nova_mask, idx_atual, true
                });
            abertos.push_back(idx_novo);
            labels_por_no[j].push_back(idx_novo);
            nova_lista.push_back(idx_novo);
            lista = std::move(nova_lista);

            // early test: fecha direto no deposito final a partir de j (mesma ideia
            // do Python), mas aqui so ATUALIZA a melhor -- nao retorna na hora --
            // para a busca continuar e exportarmos sempre a melhor coluna encontrada.
            // j != depf ja garante nova_mask com >=1 cliente aqui.
            if (j != depf && arco_permitido(j, depf)) {
                double tempo_close_bruto = tempo_chegada + s[(size_t)j] + T(j, depf);
                double tempo_close;
                if (extensao_janela(tempo_close_bruto, depf, tempo_close)) {
                    double custo_close = custo_novo + delta_rc(j, depf);
                    if (custo_close < melhor_rc) {
                        melhor_rc = custo_close;
                        auto rota_fechada = rota_forward_petro(rot, idx_novo);
                        rota_fechada.push_back(depf);
                        melhor_coluna = montar_dict(rota_fechada);
                    }
                }
            }
        }

        // poda por max_labels_por_no (mesmo mecanismo do bidirecional)
        auto& lista_no_all = labels_por_no[no_i];
        std::vector<int> lista_no;
        for (int idx : lista_no_all) {
            if (rot[(size_t)idx].ativo) lista_no.push_back(idx);
        }
        if ((int)lista_no.size() > max_labels_por_no) {
            std::sort(lista_no.begin(), lista_no.end(),
                [&](int ia, int ib) {
                    const auto& A = rot[(size_t)ia];
                    const auto& B = rot[(size_t)ib];
                    if (A.custo_mod != B.custo_mod) return A.custo_mod < B.custo_mod;
                    return A.tempo < B.tempo;
                });
            std::unordered_set<int> manter;
            for (int z = 0; z < max_labels_por_no; ++z) manter.insert(lista_no[(size_t)z]);
            for (int z = max_labels_por_no; z < (int)lista_no.size(); ++z) {
                rot[(size_t)lista_no[(size_t)z]].ativo = false;
            }
            std::vector<int> filtrada;
            for (int idx : lista_no_all) {
                if (manter.find(idx) != manter.end()) filtrada.push_back(idx);
            }
            lista_no_all = std::move(filtrada);
        }
    }

    if (!melhor_coluna.is_none() && melhor_rc < -eps) {
        return py::make_tuple(melhor_coluna, melhor_rc);
    }
    return py::make_tuple(py::none(), py::none());
}

// ===================== PETRO BIDIRECIONAL =====================
// Pricing heuristico rapido: forward e backward ate max_depth, combinacao por no comum
// e validacao exata da rota completa (multi-janela, deck load/backload, diesel e agua).
struct PetroBiLabelF {
    int no; double tempo; double soma_d; double net; double m; double diesel; double agua; double custo_mod;
    std::bitset<128> mask; int pai; bool ativo; int nvisit;
};

struct PetroBiLabelB {
    int no; double latest; double soma_d; double net; double m; double diesel; double agua; double custo_mod;
    std::bitset<128> mask; int pai; bool ativo; int nvisit;
};

static std::vector<int> rota_forward_petro_bi(const std::vector<PetroBiLabelF>& rot, int idx) {
    std::vector<int> seq;
    while (idx != -1) { seq.push_back(rot[(size_t)idx].no); idx = rot[(size_t)idx].pai; }
    std::reverse(seq.begin(), seq.end());
    return seq;
}

static std::vector<int> rota_backward_petro_bi(const std::vector<PetroBiLabelB>& rot, int idx) {
    std::vector<int> seq;
    while (idx != -1) { seq.push_back(rot[(size_t)idx].no); idx = rot[(size_t)idx].pai; }
    return seq;
}

static inline bool domina_petro_bi_b(double cA, double latestA, double mA, double cB, double latestB, double mB, double tol = 1e-6) {
    return cA <= cB + tol && latestA + tol >= latestB && mA <= mB + tol && (cA < cB - tol || latestA > latestB + tol || mA < mB - tol);
}

py::tuple sub_prog_din_bidirecional_petro(py::array_t<double, py::array::c_style | py::array::forcecast> tt, std::vector<std::vector<double>> aw, std::vector<std::vector<double>> bw, std::vector<double> s, std::vector<double> d_deck, std::vector<double> b_deck, std::vector<double> d_diesel, std::vector<double> d_agua, std::vector<int> plataforma_id, std::vector<double> pi, double sigma_k, double cap_deck, double cap_diesel, double cap_agua, int nbcd, int dep0, int depf, std::vector<double> mu_flat, std::vector<std::uint8_t> forbid_flat, std::vector<int> req_i, std::vector<int> req_j, int max_labels_por_no = 200, int max_depth = -1, long long max_combinacoes = 200000, double eps = 1e-6) {
    if (tt.ndim() != 2) throw std::runtime_error("tt must be 2D (nbn x nbn)");
    auto T = tt.unchecked<2>();
    int nbn = (int)T.shape(0);
    if ((int)T.shape(1) != nbn) throw std::runtime_error("tt must be square");
    if ((int)aw.size() != nbn || (int)bw.size() != nbn) throw std::runtime_error("aw,bw must have size nbn");
    if ((int)s.size() != nbn || (int)d_deck.size() != nbn || (int)b_deck.size() != nbn || (int)d_diesel.size() != nbn || (int)d_agua.size() != nbn) throw std::runtime_error("resource arrays must have size nbn");
    if ((int)plataforma_id.size() != nbn) throw std::runtime_error("plataforma_id must have size nbn");
    for (int c = 1; c <= nbcd; ++c) if (plataforma_id[(size_t)c] < 0) throw std::runtime_error("plataforma_id must be nonnegative for every client");
    if ((int)pi.size() != nbcd) throw std::runtime_error("pi must have size nbcd");
    if (!mu_flat.empty() && (int)mu_flat.size() != nbn * nbn) throw std::runtime_error("mu_flat must have size nbn*nbn");
    if (!forbid_flat.empty() && (int)forbid_flat.size() != nbn * nbn) throw std::runtime_error("forbid_flat must have size nbn*nbn");
    if (req_i.size() != req_j.size()) throw std::runtime_error("req_i and req_j must have same length");
    if (max_depth < 0) max_depth = (nbcd + 2) / 2;
    if (max_labels_por_no < 1) max_labels_por_no = 1;
    if (max_combinacoes < 1) max_combinacoes = 1;
    if (mu_flat.empty()) mu_flat.assign((size_t)nbn * (size_t)nbn, 0.0);
    if (forbid_flat.empty()) forbid_flat.assign((size_t)nbn * (size_t)nbn, 0);

    std::unordered_set<std::uint64_t> fixados_k;
    std::unordered_map<int, int> succ_fixo, pred_fixo;
    for (size_t z = 0; z < req_i.size(); ++z) {
        int i = req_i[z], j = req_j[z];
        fixados_k.insert(arc_key(i, j));
        auto its = succ_fixo.find(i); if (its != succ_fixo.end() && its->second != j) return py::make_tuple(py::none(), py::none());
        auto itp = pred_fixo.find(j); if (itp != pred_fixo.end() && itp->second != i) return py::make_tuple(py::none(), py::none());
        succ_fixo[i] = j; pred_fixo[j] = i;
    }

    auto idx2 = [&](int i, int j) -> size_t { return (size_t)i * (size_t)nbn + (size_t)j; };
    auto arco_permitido = [&](int i, int j) -> bool {
        if (forbid_flat[idx2(i, j)] != 0) return false;
        auto its = succ_fixo.find(i); if (its != succ_fixo.end() && its->second != j) return false;
        auto itp = pred_fixo.find(j); if (itp != pred_fixo.end() && itp->second != i) return false;
        return true;
        };
    auto delta_rc = [&](int i, int j) -> double {
        double v = T(i, j) - mu_flat[idx2(i, j)];
        if (1 <= j && j <= nbcd) v -= pi[(size_t)(j - 1)];
        if (j == depf) v -= sigma_k;
        return v;
        };
    const double EPS_WIN = 1e-6;
    auto earliest_start = [&](double chegada, int j, double& inicio) -> bool {
        const auto& aj = aw[(size_t)j]; const auto& bj = bw[(size_t)j];
        for (size_t r = 0; r < bj.size(); ++r) {
            double a = r < aj.size() ? aj[r] : 0.0;
            double ini = std::max(chegada, a);
            if (ini + s[(size_t)j] <= bj[r] + EPS_WIN) { inicio = ini; return true; }
        }
        return false;
        };
    auto latest_start_node = [&](int i, double limite_saida, double& latest) -> bool {
        const auto& ai = aw[(size_t)i]; const auto& bi = bw[(size_t)i];
        bool ok = false; double best = -std::numeric_limits<double>::infinity();
        for (size_t r = 0; r < bi.size(); ++r) {
            double a = r < ai.size() ? ai[r] : 0.0;
            double cand = std::min(bi[r] - s[(size_t)i], limite_saida);
            if (cand + EPS_WIN >= a && cand > best) { best = cand; ok = true; }
        }
        if (ok) latest = best;
        return ok;
        };
    auto todos_fixados = [&](const std::vector<int>& rota) -> bool {
        if (fixados_k.empty()) return true;
        std::unordered_set<std::uint64_t> arcos;
        for (size_t t = 0; t + 1 < rota.size(); ++t) arcos.insert(arc_key(rota[t], rota[t + 1]));
        for (const auto& a : fixados_k) if (arcos.find(a) == arcos.end()) return false;
        return true;
        };
    auto avaliar_rota = [&](const std::vector<int>& rota) -> py::tuple {
        if (rota.size() < 3 || rota.front() != dep0 || rota.back() != depf) return py::make_tuple(py::none(), py::none());
        if (!petro_ordem_plataformas_valida(rota, plataforma_id, d_deck, b_deck, d_diesel, d_agua, nbcd)) return py::make_tuple(py::none(), py::none());
        std::unordered_set<int> visitados;
        double tempo = std::max(aw[(size_t)dep0].empty() ? 0.0 : aw[(size_t)dep0][0], 0.0);
        double soma_d = 0.0, net = 0.0, pico = 0.0, diesel = 0.0, agua = 0.0, custo_real = 0.0, custo_red = 0.0;
        for (size_t t = 0; t + 1 < rota.size(); ++t) {
            int i = rota[t], j = rota[t + 1];
            if (i == j || !arco_permitido(i, j)) return py::make_tuple(py::none(), py::none());
            double inicio_j;
            if (!earliest_start(tempo + s[(size_t)i] + T(i, j), j, inicio_j)) return py::make_tuple(py::none(), py::none());
            tempo = inicio_j;
            if (1 <= j && j <= nbcd) {
                if (!visitados.insert(j).second) return py::make_tuple(py::none(), py::none());
                pico = std::max(pico, net + b_deck[(size_t)j]);
                net += b_deck[(size_t)j] - d_deck[(size_t)j];
                soma_d += d_deck[(size_t)j]; diesel += d_diesel[(size_t)j]; agua += d_agua[(size_t)j];
                if (soma_d + pico > cap_deck + 1e-9 || diesel > cap_diesel + 1e-9 || agua > cap_agua + 1e-9) return py::make_tuple(py::none(), py::none());
            }
            custo_real += T(i, j); custo_red += delta_rc(i, j);
        }
        if (visitados.empty() || !todos_fixados(rota)) return py::make_tuple(py::none(), py::none());
        std::vector<int> bin((size_t)nbcd, 0); for (int v : visitados) bin[(size_t)(v - 1)] = 1;
        py::dict out; out["clientes"] = rota; out["custo"] = custo_real; out["bin_xij"] = bin;
        return py::make_tuple(out, custo_red);
        };

    double tempo0 = std::max(aw[(size_t)dep0].empty() ? 0.0 : aw[(size_t)dep0][0], 0.0);
    std::vector<PetroBiLabelF> rot_f;
    std::deque<int> abertos_f;
    std::unordered_map<int, std::vector<int>> labels_f_por_no;
    std::unordered_map<NodeMaskKey, std::vector<int>, NodeMaskKeyHash> fronteira_f;
    rot_f.push_back(PetroBiLabelF{ dep0, tempo0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, std::bitset<128>(), -1, true, 0 });
    abertos_f.push_back(0); labels_f_por_no[dep0].push_back(0); fronteira_f[{dep0, std::bitset<128>()}].push_back(0);

    while (!abertos_f.empty()) {
        int idx = abertos_f.front(); abertos_f.pop_front();
        PetroBiLabelF r = rot_f[(size_t)idx]; if (!r.ativo || r.nvisit >= max_depth) continue;
        std::vector<int> candidatos;
        auto its = succ_fixo.find(r.no);
        if (its != succ_fixo.end()) { if (1 <= its->second && its->second <= nbcd) candidatos.push_back(its->second); }
        else for (int j = 1; j <= nbcd; ++j) if (!(r.mask & cliente_mask(j)).any()) candidatos.push_back(j);
        std::sort(candidatos.begin(), candidatos.end(), [&](int x, int y) { return delta_rc(r.no, x) < delta_rc(r.no, y); });
        for (int j : candidatos) {
            if (!arco_permitido(r.no, j) || (r.mask & cliente_mask(j)).any()) continue;
            if (!petro_extensao_forward_plataforma_valida(
                r.no, j, r.mask, plataforma_id, d_deck, b_deck, d_diesel, d_agua, nbcd)) continue;
            auto nm = r.mask | cliente_mask(j);
            double soma_d = r.soma_d + d_deck[(size_t)j];
            double pico = std::max(r.m, r.net + b_deck[(size_t)j]);
            double net = r.net + b_deck[(size_t)j] - d_deck[(size_t)j];
            double diesel = r.diesel + d_diesel[(size_t)j], agua = r.agua + d_agua[(size_t)j];
            if (soma_d + pico > cap_deck + 1e-9 || diesel > cap_diesel + 1e-9 || agua > cap_agua + 1e-9) continue;
            double tempo; if (!earliest_start(r.tempo + s[(size_t)r.no] + T(r.no, j), j, tempo)) continue;
            double custo = r.custo_mod + delta_rc(r.no, j);
            NodeMaskKey chave{ j, nm }; auto& lista = fronteira_f[chave]; bool dominado = false;
            for (int io : lista) { const auto& o = rot_f[(size_t)io]; if (o.ativo && domina_petro(o.custo_mod, o.tempo, o.m, custo, tempo, pico)) { dominado = true; break; } }
            if (dominado) continue;
            std::vector<int> nova; nova.reserve(lista.size() + 1);
            for (int io : lista) { auto& o = rot_f[(size_t)io]; if (!o.ativo) continue; if (domina_petro(custo, tempo, pico, o.custo_mod, o.tempo, o.m)) o.ativo = false; else nova.push_back(io); }
            int in = (int)rot_f.size(); rot_f.push_back(PetroBiLabelF{ j, tempo, soma_d, net, pico, diesel, agua, custo, nm, idx, true, r.nvisit + 1 });
            abertos_f.push_back(in); labels_f_por_no[j].push_back(in); nova.push_back(in); lista = std::move(nova);
        }
        auto& all = labels_f_por_no[r.no]; std::vector<int> ativos;
        for (int z : all) if (rot_f[(size_t)z].ativo) ativos.push_back(z);
        if ((int)ativos.size() > max_labels_por_no) {
            std::sort(ativos.begin(), ativos.end(), [&](int a, int b) { const auto& A = rot_f[(size_t)a]; const auto& B = rot_f[(size_t)b]; if (A.custo_mod != B.custo_mod) return A.custo_mod < B.custo_mod; if (A.tempo != B.tempo) return A.tempo < B.tempo; return A.m < B.m; });
            std::unordered_set<int> manter; for (int z = 0; z < max_labels_por_no; ++z) manter.insert(ativos[(size_t)z]);
            for (int z = max_labels_por_no; z < (int)ativos.size(); ++z) rot_f[(size_t)ativos[(size_t)z]].ativo = false;
            std::vector<int> fil; for (int z : all) if (manter.find(z) != manter.end()) fil.push_back(z); all = std::move(fil);
        }
    }

    double latest_depf;
    if (!latest_start_node(depf, std::numeric_limits<double>::infinity(), latest_depf)) return py::make_tuple(py::none(), py::none());
    std::vector<PetroBiLabelB> rot_b;
    std::deque<int> abertos_b;
    std::unordered_map<int, std::vector<int>> labels_b_por_no;
    std::unordered_map<NodeMaskKey, std::vector<int>, NodeMaskKeyHash> fronteira_b;
    rot_b.push_back(PetroBiLabelB{ depf, latest_depf, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, std::bitset<128>(), -1, true, 0 });
    abertos_b.push_back(0); labels_b_por_no[depf].push_back(0); fronteira_b[{depf, std::bitset<128>()}].push_back(0);

    while (!abertos_b.empty()) {
        int idx = abertos_b.front(); abertos_b.pop_front();
        PetroBiLabelB r = rot_b[(size_t)idx]; if (!r.ativo || r.nvisit >= max_depth) continue;
        std::vector<int> candidatos;
        auto itp = pred_fixo.find(r.no);
        if (itp != pred_fixo.end()) { if (1 <= itp->second && itp->second <= nbcd) candidatos.push_back(itp->second); }
        else for (int i = 1; i <= nbcd; ++i) if (!(r.mask & cliente_mask(i)).any()) candidatos.push_back(i);
        std::sort(candidatos.begin(), candidatos.end(), [&](int x, int y) { return delta_rc(x, r.no) < delta_rc(y, r.no); });
        for (int i : candidatos) {
            if (!arco_permitido(i, r.no) || (r.mask & cliente_mask(i)).any()) continue;
            if (!petro_extensao_backward_plataforma_valida(
                i, r.no, r.mask, plataforma_id, d_deck, b_deck, d_diesel, d_agua, nbcd)) continue;
            auto nm = r.mask | cliente_mask(i);
            double soma_d = d_deck[(size_t)i] + r.soma_d;
            double net_i = b_deck[(size_t)i] - d_deck[(size_t)i];
            double pico = std::max(b_deck[(size_t)i], net_i + r.m);
            double net = net_i + r.net;
            double diesel = d_diesel[(size_t)i] + r.diesel, agua = d_agua[(size_t)i] + r.agua;
            if (soma_d + pico > cap_deck + 1e-9 || diesel > cap_diesel + 1e-9 || agua > cap_agua + 1e-9) continue;
            double latest; if (!latest_start_node(i, r.latest - s[(size_t)i] - T(i, r.no), latest)) continue;
            double custo = delta_rc(i, r.no) + r.custo_mod;
            NodeMaskKey chave{ i, nm }; auto& lista = fronteira_b[chave]; bool dominado = false;
            for (int io : lista) { const auto& o = rot_b[(size_t)io]; if (o.ativo && domina_petro_bi_b(o.custo_mod, o.latest, o.m, custo, latest, pico)) { dominado = true; break; } }
            if (dominado) continue;
            std::vector<int> nova; nova.reserve(lista.size() + 1);
            for (int io : lista) { auto& o = rot_b[(size_t)io]; if (!o.ativo) continue; if (domina_petro_bi_b(custo, latest, pico, o.custo_mod, o.latest, o.m)) o.ativo = false; else nova.push_back(io); }
            int in = (int)rot_b.size(); rot_b.push_back(PetroBiLabelB{ i, latest, soma_d, net, pico, diesel, agua, custo, nm, idx, true, r.nvisit + 1 });
            abertos_b.push_back(in); labels_b_por_no[i].push_back(in); nova.push_back(in); lista = std::move(nova);
        }
        auto& all = labels_b_por_no[r.no]; std::vector<int> ativos;
        for (int z : all) if (rot_b[(size_t)z].ativo) ativos.push_back(z);
        if ((int)ativos.size() > max_labels_por_no) {
            std::sort(ativos.begin(), ativos.end(), [&](int a, int b) { const auto& A = rot_b[(size_t)a]; const auto& B = rot_b[(size_t)b]; if (A.custo_mod != B.custo_mod) return A.custo_mod < B.custo_mod; if (A.latest != B.latest) return A.latest > B.latest; return A.m < B.m; });
            std::unordered_set<int> manter; for (int z = 0; z < max_labels_por_no; ++z) manter.insert(ativos[(size_t)z]);
            for (int z = max_labels_por_no; z < (int)ativos.size(); ++z) rot_b[(size_t)ativos[(size_t)z]].ativo = false;
            std::vector<int> fil; for (int z : all) if (manter.find(z) != manter.end()) fil.push_back(z); all = std::move(fil);
        }
    }

    py::object melhor_coluna = py::none();
    double melhor_rc = std::numeric_limits<double>::infinity();
    long long combinacoes = 0;
    for (int m = 1; m <= nbcd && combinacoes < max_combinacoes; ++m) {
        auto itf = labels_f_por_no.find(m), itb = labels_b_por_no.find(m);
        if (itf == labels_f_por_no.end() || itb == labels_b_por_no.end()) continue;
        for (int fi : itf->second) {
            const auto& rf = rot_f[(size_t)fi]; if (!rf.ativo) continue;
            for (int bi : itb->second) {
                if (++combinacoes > max_combinacoes) break;
                const auto& rb = rot_b[(size_t)bi]; if (!rb.ativo) continue;
                if ((rf.mask & rb.mask) != cliente_mask(m)) continue;
                if (rf.tempo > rb.latest + EPS_WIN) continue;
                if (rf.diesel + rb.diesel - d_diesel[(size_t)m] > cap_diesel + 1e-9) continue;
                if (rf.agua + rb.agua - d_agua[(size_t)m] > cap_agua + 1e-9) continue;
                double rc_estimado = rf.custo_mod + rb.custo_mod;
                if (rc_estimado >= -eps || rc_estimado >= melhor_rc - 1e-12) continue;
                auto rota_f = rota_forward_petro_bi(rot_f, fi);
                auto rota_b = rota_backward_petro_bi(rot_b, bi);
                if (!rota_b.empty()) rota_b.erase(rota_b.begin());
                std::vector<int> rota; rota.reserve(rota_f.size() + rota_b.size());
                rota.insert(rota.end(), rota_f.begin(), rota_f.end()); rota.insert(rota.end(), rota_b.begin(), rota_b.end());
                auto aval = avaliar_rota(rota); py::object col = aval[0]; if (col.is_none()) continue;
                double rc = aval[1].cast<double>(); if (rc < melhor_rc) { melhor_rc = rc; melhor_coluna = col; }
            }
        }
    }

    for (const auto& kv : labels_f_por_no) {
        int no = kv.first; if (no == dep0 || no == depf || !arco_permitido(no, depf)) continue;
        for (int fi : kv.second) {
            if (!rot_f[(size_t)fi].ativo) continue;
            auto rota = rota_forward_petro_bi(rot_f, fi); rota.push_back(depf);
            auto aval = avaliar_rota(rota); py::object col = aval[0]; if (col.is_none()) continue;
            double rc = aval[1].cast<double>(); if (rc < melhor_rc) { melhor_rc = rc; melhor_coluna = col; }
        }
    }

    if (!melhor_coluna.is_none() && melhor_rc < -eps) return py::make_tuple(melhor_coluna, melhor_rc);
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

    m.def("sub_prog_din_bidirecional_petro", &sub_prog_din_bidirecional_petro,
        py::arg("tt"), py::arg("aw"), py::arg("bw"), py::arg("s"), py::arg("d_deck"), py::arg("b_deck"), py::arg("d_diesel"), py::arg("d_agua"), py::arg("plataforma_id"), py::arg("pi"), py::arg("sigma_k"), py::arg("cap_deck"), py::arg("cap_diesel"), py::arg("cap_agua"), py::arg("nbcd"), py::arg("dep0"), py::arg("depf"), py::arg("mu_flat") = std::vector<double>{}, py::arg("forbid_flat") = std::vector<std::uint8_t>{}, py::arg("req_i") = std::vector<int>{}, py::arg("req_j") = std::vector<int>{}, py::arg("max_labels_por_no") = 200, py::arg("max_depth") = -1, py::arg("max_combinacoes") = 200000, py::arg("eps") = 1e-6);

    m.def("sub_prog_din_petro", &sub_prog_din_petro,
        py::arg("tt"),
        py::arg("aw"),
        py::arg("bw"),
        py::arg("s"),
        py::arg("d_deck"),
        py::arg("b_deck"),
        py::arg("d_diesel"),
        py::arg("d_agua"),
        py::arg("plataforma_id"),
        py::arg("pi"),
        py::arg("sigma_k"),
        py::arg("cap_deck"),
        py::arg("cap_diesel"),
        py::arg("cap_agua"),
        py::arg("nbcd"),
        py::arg("dep0"),
        py::arg("depf"),
        py::arg("mu_flat") = std::vector<double>{},
        py::arg("forbid_flat") = std::vector<std::uint8_t>{},
        py::arg("req_i") = std::vector<int>{},
        py::arg("req_j") = std::vector<int>{},
        py::arg("max_labels_por_no") = 200,
        py::arg("eps") = 1e-6
    );
}