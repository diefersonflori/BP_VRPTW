// vrptw_pd.cpp  (compile como .pyd via pybind11)
// Exporta:
//   - hello() -> string
//   - SUB_PROG_DIN(tt,a,b,s,d,pi,sigma_k,cap_k, arcos_proibidos, arcos_fixados) -> (dict, custo_red) ou (None,None)

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <vector>
#include <deque>
#include <unordered_map>
#include <unordered_set>
#include <cstdint>
#include <cmath>
#include <limits>
#include <string>
#include <stdexcept>

namespace py = pybind11;

std::string hello() { return "Hello WorldPD! (from .pyd)"; }

// ------------------ helpers ------------------

static inline std::uint64_t cliente_mask(int c) {
    // cliente c em [1..nbcd] -> bit (c-1)
    return 1ULL << (c - 1);
}

static inline bool domina(double cA, double tA, double qA,
    double cB, double tB, double qB,
    double tol) {
    // A domina B se <= em tudo e < em pelo menos 1
    bool le_all =
        (cA <= cB + tol) &&
        (tA <= tB + tol) &&
        (qA <= qB + tol);

    bool lt_one =
        (cA < cB - tol) ||
        (tA < tB - tol) ||
        (qA < qB - tol);

    return le_all && lt_one;
}

// arco (i,j) em um uint64: (i<<32) | j
static inline std::uint64_t arc_key(int i, int j) {
    return ((std::uint64_t)(std::uint32_t)i << 32) | (std::uint32_t)j;
}

// ------------------ estruturas ------------------

struct Label {
    int no;
    double tempo;
    double carga;
    double custo_mod;
    std::uint64_t mask;      // clientes
    std::uint64_t mask_fix;  // arcos fixos cumpridos
    int pai;                 // índice do label pai, -1 se nenhum
    bool ativo;
};

// chave (no, mask, mask_fix) para unordered_map
struct StateKey {
    int no;
    std::uint64_t mask;
    std::uint64_t mask_fix;
    bool operator==(const StateKey& o) const noexcept {
        return no == o.no && mask == o.mask && mask_fix == o.mask_fix;
    }
};

struct StateKeyHash {
    std::size_t operator()(const StateKey& k) const noexcept {
        std::uint64_t x = (std::uint64_t)(std::uint32_t)k.no;
        x = x * 1315423911ULL + k.mask;
        x ^= (x >> 33);
        x *= 0xff51afd7ed558ccdULL;
        x ^= (x >> 33);

        std::uint64_t y = k.mask_fix;
        y ^= (y >> 33);
        y *= 0xc4ceb9fe1a85ec53ULL;
        y ^= (y >> 33);

        x ^= y + 0x9e3779b97f4a7c15ULL + (x << 6) + (x >> 2);
        return (std::size_t)x;
    }
};

// ------------------ PD / Pricing ------------------

py::tuple SUB_PROG_DIN(
    py::array_t<double, py::array::c_style | py::array::forcecast> tt,   // nbn x nbn
    py::array_t<double, py::array::c_style | py::array::forcecast> a,    // nbn
    py::array_t<double, py::array::c_style | py::array::forcecast> b,    // nbn
    py::array_t<double, py::array::c_style | py::array::forcecast> s,    // nbn
    py::array_t<double, py::array::c_style | py::array::forcecast> d,    // nbn
    py::array_t<double, py::array::c_style | py::array::forcecast> pi,   // nbcd
    double sigma_k,
    double cap_k,
    py::array_t<int, py::array::c_style | py::array::forcecast> arcos_proibidos, // mp x 2
    py::array_t<int, py::array::c_style | py::array::forcecast> arcos_fixados    // mf x 2
) {
    // ------------------ validação básica ------------------
    if (tt.ndim() != 2) throw std::runtime_error("tt deve ser 2D (nbn x nbn)");
    if (a.ndim() != 1 || b.ndim() != 1 || s.ndim() != 1 || d.ndim() != 1)
        throw std::runtime_error("a,b,s,d devem ser 1D");
    if (pi.ndim() != 1) throw std::runtime_error("pi deve ser 1D");

    if (arcos_proibidos.ndim() != 2 || arcos_proibidos.shape(1) != 2)
        throw std::runtime_error("arcos_proibidos deve ser mp x 2");
    if (arcos_fixados.ndim() != 2 || arcos_fixados.shape(1) != 2)
        throw std::runtime_error("arcos_fixados deve ser mf x 2");

    auto TT = tt.unchecked<2>();
    auto A = a.unchecked<1>();
    auto B = b.unchecked<1>();
    auto S = s.unchecked<1>();
    auto D = d.unchecked<1>();
    auto PI = pi.unchecked<1>();
    auto F = arcos_proibidos.unchecked<2>();
    auto FX = arcos_fixados.unchecked<2>();

    const int nbn = (int)TT.shape(0);
    const int nbn2 = (int)TT.shape(1);
    if (nbn != nbn2) throw std::runtime_error("tt deve ser quadrada (nbn x nbn)");
    if ((int)A.shape(0) != nbn || (int)B.shape(0) != nbn || (int)S.shape(0) != nbn || (int)D.shape(0) != nbn)
        throw std::runtime_error("a,b,s,d devem ter tamanho nbn");

    const int nbcd = (int)PI.shape(0);
    if (nbcd > 63) throw std::runtime_error("nbcd > 63: mascara uint64_t nao suporta (ajustar depois).");

    const int mf = (int)FX.shape(0);
    if (mf > 63) throw std::runtime_error("mf (arcos_fixados) > 63: mask_fix uint64_t nao suporta (ajustar depois).");

    const int dep0 = 0;
    const int depf = nbn - 1;

    // ------------------ arcos proibidos -> unordered_set ------------------
    std::unordered_set<std::uint64_t> proib;
    proib.reserve((std::size_t)F.shape(0) * 2 + 32);
    for (size_t r = 0; r < F.shape(0); ++r) {
        int i = F(r, 0);
        int j = F(r, 1);
        proib.insert(arc_key(i, j));
    }

    // ------------------ fixos -> índice arc_key -> pos (bit) ------------------
    std::unordered_map<std::uint64_t, int> idx_fixo;
    idx_fixo.reserve((std::size_t)mf * 2 + 8);

    for (size_t r = 0; r < FX.shape(0); ++r) {
        int i = FX(r, 0);
        int j = FX(r, 1);
        idx_fixo[arc_key(i, j)] = (int)r; // bit r
    }

    const std::uint64_t ALL_FIX = (mf == 0) ? 0ULL : ((1ULL << mf) - 1ULL);

    // ------------------ estruturas PD ------------------
    const double tol = 1e-6;

    std::unordered_map<StateKey, std::vector<int>, StateKeyHash> fronteira;
    fronteira.reserve(200000);

    std::vector<Label> rotulos;
    rotulos.reserve(300000);

    std::deque<int> abertos;

    // rótulo inicial
    double tempo_inicial = A(dep0);
    if (tempo_inicial < 0.0) tempo_inicial = 0.0;

    Label r0;
    r0.no = dep0;
    r0.tempo = tempo_inicial;
    r0.carga = 0.0;
    r0.custo_mod = 0.0;
    r0.mask = 0ULL;
    r0.mask_fix = 0ULL;
    r0.pai = -1;
    r0.ativo = true;

    rotulos.push_back(r0);
    abertos.push_back(0);
    fronteira[{dep0, 0ULL, 0ULL}] = std::vector<int>{ 0 };

    int melhor_indice = -1;
    double melhor_custo_reduzido = std::numeric_limits<double>::infinity();

    // libera GIL durante o loop pesado
    py::gil_scoped_release release;

    // ------------------ LOOP PRINCIPAL ------------------
    while (!abertos.empty()) {
        int idx_atual = abertos.front();
        abertos.pop_front();

        Label& r_atual = rotulos[idx_atual];
        if (!r_atual.ativo) continue;

        int no_i = r_atual.no;
        double tempo_i = r_atual.tempo;
        double carga_i = r_atual.carga;
        double custo_mod_i = r_atual.custo_mod;
        std::uint64_t mask_i = r_atual.mask;
        std::uint64_t mask_fix_i = r_atual.mask_fix;

        // chegou no depósito final: só aceita se cumpriu TODOS os fixos
        if (no_i == depf) {
            if (mask_fix_i != ALL_FIX) continue;
            if (custo_mod_i < melhor_custo_reduzido) {
                melhor_custo_reduzido = custo_mod_i;
                melhor_indice = idx_atual;
            }
            continue;
        }

        // --------- candidatos: clientes não visitados e não proibidos + (depf se ALL_FIX) ---------
        std::vector<int> candidatos;
        candidatos.reserve((std::size_t)nbcd + 1);

        for (int c = 1; c <= nbcd; ++c) {
            if ((mask_i & cliente_mask(c)) != 0ULL) continue;
            if (proib.find(arc_key(no_i, c)) != proib.end()) continue;
            candidatos.push_back(c);
        }

        if (mask_fix_i == ALL_FIX && proib.find(arc_key(no_i, depf)) == proib.end()) {
            candidatos.push_back(depf);
        }

        // --------- expansão ---------
        for (int j : candidatos) {
            // arco proibido (segurança)
            if (proib.find(arc_key(no_i, j)) != proib.end()) continue;

            // atualiza mask_fix se esse arco for fixado
            std::uint64_t nova_mask_fix = mask_fix_i;
            auto itfix = idx_fixo.find(arc_key(no_i, j));
            if (itfix != idx_fixo.end()) {
                int pos = itfix->second;
                nova_mask_fix |= (1ULL << pos);
            }

            // máscara clientes
            std::uint64_t nova_mask = mask_i;
            if (1 <= j && j <= nbcd) {
                std::uint64_t bit = cliente_mask(j);
                if ((mask_i & bit) != 0ULL) continue;
                nova_mask = mask_i | bit;
            }

            // capacidade
            double nova_carga = carga_i;
            if (1 <= j && j <= nbcd) {
                nova_carga += D(j);
            }
            if (nova_carga > cap_k) continue;

            // janela de tempo
            double tempo_chegada = tempo_i + S(no_i) + TT(no_i, j);
            if (tempo_chegada < A(j)) tempo_chegada = A(j);
            if (tempo_chegada > B(j)) continue;

            // custo reduzido
            double custo_mod_novo = custo_mod_i + TT(no_i, j);
            if (1 <= j && j <= nbcd) custo_mod_novo -= PI(j - 1);
            if (j == depf) custo_mod_novo -= sigma_k;

            // dominância
            StateKey chave{ j, nova_mask, nova_mask_fix };
            auto it = fronteira.find(chave);

            if (it == fronteira.end()) {
                Label novo;
                novo.no = j;
                novo.tempo = tempo_chegada;
                novo.carga = nova_carga;
                novo.custo_mod = custo_mod_novo;
                novo.mask = nova_mask;
                novo.mask_fix = nova_mask_fix;
                novo.pai = idx_atual;
                novo.ativo = true;

                int idx_novo = (int)rotulos.size();
                rotulos.push_back(novo);
                abertos.push_back(idx_novo);

                fronteira.emplace(chave, std::vector<int>{idx_novo});
                continue;
            }

            std::vector<int>& lista = it->second;

            // 1) se alguém domina o novo -> descarta
            bool dominado = false;
            for (int idx_old : lista) {
                Label& r_old = rotulos[idx_old];
                if (!r_old.ativo) continue;

                if (domina(r_old.custo_mod, r_old.tempo, r_old.carga,
                    custo_mod_novo, tempo_chegada, nova_carga, tol)) {
                    dominado = true;
                    break;
                }
            }
            if (dominado) continue;

            // 2) novo domina alguns -> desativa eles
            std::vector<int> nova_lista;
            nova_lista.reserve(lista.size() + 1);

            for (int idx_old : lista) {
                Label& r_old = rotulos[idx_old];
                if (!r_old.ativo) continue;

                if (domina(custo_mod_novo, tempo_chegada, nova_carga,
                    r_old.custo_mod, r_old.tempo, r_old.carga, tol)) {
                    r_old.ativo = false;
                }
                else {
                    nova_lista.push_back(idx_old);
                }
            }

            // 3) cria rótulo
            Label novo;
            novo.no = j;
            novo.tempo = tempo_chegada;
            novo.carga = nova_carga;
            novo.custo_mod = custo_mod_novo;
            novo.mask = nova_mask;
            novo.mask_fix = nova_mask_fix;
            novo.pai = idx_atual;
            novo.ativo = true;

            int idx_novo = (int)rotulos.size();
            rotulos.push_back(novo);
            abertos.push_back(idx_novo);

            nova_lista.push_back(idx_novo);
            lista.swap(nova_lista);
        }
    }

    // volta GIL
    py::gil_scoped_acquire acquire;

    // ------------------ PÓS ------------------
    if (melhor_indice == -1) return py::make_tuple(py::none(), py::none());
    if (melhor_custo_reduzido >= -1e-6) return py::make_tuple(py::none(), py::none());

    // reconstrói rota
    std::vector<int> rota_reversa;
    int idx = melhor_indice;
    while (idx != -1) {
        rota_reversa.push_back(rotulos[idx].no);
        idx = rotulos[idx].pai;
    }
    std::vector<int> rota;
    rota.reserve(rota_reversa.size());
    for (int i = (int)rota_reversa.size() - 1; i >= 0; --i) rota.push_back(rota_reversa[i]);

    // custo real
    double custo_real = 0.0;
    for (std::size_t i = 0; i + 1 < rota.size(); ++i) {
        custo_real += TT(rota[i], rota[i + 1]);
    }

    // bin_xij
    std::vector<int> bin_xij((std::size_t)nbcd, 0);
    for (int v : rota) {
        if (1 <= v && v <= nbcd) bin_xij[(std::size_t)(v - 1)] = 1;
    }

    py::dict rota_dict;
    rota_dict["clientes"] = rota;
    rota_dict["custo"] = custo_real;
    rota_dict["bin_xij"] = bin_xij;

    return py::make_tuple(rota_dict, melhor_custo_reduzido);
}

// ------------------ módulo ------------------

PYBIND11_MODULE(vrptw_pd, m) {
    m.def("hello", &hello);
    m.def("SUB_PROG_DIN", &SUB_PROG_DIN,
        py::arg("tt"), py::arg("a"), py::arg("b"), py::arg("s"), py::arg("d"),
        py::arg("pi"), py::arg("sigma_k"), py::arg("cap_k"),
        py::arg("arcos_proibidos"), py::arg("arcos_fixados"));
}
