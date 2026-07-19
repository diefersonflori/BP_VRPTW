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

static inline std::uint64_t cust_bit(int c) {
    // c em [1..nbcd] -> bit (c-1)
    return 1ULL << (std::uint64_t)(c - 1);
}

static inline std::uint64_t arc_key(int i, int j) {
    return (std::uint64_t(std::uint32_t(i)) << 32) | std::uint64_t(std::uint32_t(j));
}

std::string hello() { return "vrptw_pd ok"; }

// ------------------ estado de DFS ------------------

struct Step {
    int node;
    double t;
    double q;
    double rc;
    std::uint64_t mask;
};

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
        std::uint64_t mask;
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
        std::uint64_t bit = cust_bit(c);
        if (cur.mask & bit) continue;

        std::uint64_t nm = cur.mask | bit;

        double nq = cur.q + d[(size_t)c];
        if (nq > cap_k + 1e-9) continue;

        double arrive = cur.t + s[(size_t)i] + T(i, c);
        if (arrive < a[(size_t)c]) arrive = a[(size_t)c];
        if (arrive > b[(size_t)c] + 1e-9) continue;

        feas.push_back(Cand{ c, arrive, nq, nm, delta_rc(i, c) });
    }

    // depósito final (bloqueia rota vazia 0->depf)
    if (cur.mask != 0ULL) {
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

    // máscara usa uint64 => suporta até 63 clientes
    if (nbcd > 63) throw std::runtime_error("nbcd > 63 not supported by uint64 mask");

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
        start.mask = 0ULL;

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
        std::uint64_t mask;
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
        if (cur.mask & cust_bit(c)) continue;
        if (is_forbidden(i, c)) continue;

        std::uint64_t nm = cur.mask | cust_bit(c);
        std::uint32_t nrm = upd_req(req_mask, i, c);

        double nq = cur.q + d[(size_t)c];
        if (nq > cap_k + 1e-9) continue;

        double arrive = cur.t + s[(size_t)i] + T(i, c);
        if (arrive < a[(size_t)c]) arrive = a[(size_t)c];
        if (arrive > b[(size_t)c] + 1e-9) continue;

        feas.push_back(Cand{ c, arrive, nq, nm, nrm, delta_rc(i, c) });
    }

    // depf: só deixa fechar se req completo e não vazia
    if (cur.mask != 0ULL && !is_forbidden(i, depf)) {
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
    if (nbcd > 63) throw std::runtime_error("nbcd > 63 not supported by uint64 mask");

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
        start.mask = 0ULL;

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

PYBIND11_MODULE(vrptw_pd, m) {
    m.def("hello", &hello);

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