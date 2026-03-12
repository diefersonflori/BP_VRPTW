#include <bits/stdc++.h>
using namespace std;

struct NodeData {
    double a, b, s, d;
};

struct Label {
    int node;
    double time;
    double load;
    double cost_mod;
    uint64_t mask;
    int parent;   // índice do rótulo pai, -1 se raiz
    bool active;
};

static inline bool domina(double cA, double tA, double qA,
                          double cB, double tB, double qB,
                          double tol = 1e-6) {
    return (cA <= cB + tol &&
            tA <= tB + tol &&
            qA <= qB + tol &&
            (cA < cB - tol || tA < tB - tol || qA < qB - tol));
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int nbn, nbcd;
    if (!(cin >> nbn >> nbcd)) {
        cerr << "ERR header\n";
        return 2;
    }

    int k;
    double cap_k, velocidade, sigma_k;
    cin >> k >> cap_k >> velocidade >> sigma_k;

    vector<double> pi(nbcd, 0.0);
    for (int i = 0; i < nbcd; i++) cin >> pi[i];

    vector<NodeData> nd(nbn);
    for (int i = 0; i < nbn; i++) {
        cin >> nd[i].a >> nd[i].b >> nd[i].s >> nd[i].d;
    }

    vector<vector<double>> dist(nbn, vector<double>(nbn, 0.0));
    for (int i = 0; i < nbn; i++)
        for (int j = 0; j < nbn; j++)
            cin >> dist[i][j];

    const int dep0 = 0;
    const int depf = nbn - 1;

    auto travel_time = [&](int i, int j) -> double {
        return dist[i][j] / velocidade;
    };

    auto cliente_mask = [&](int c) -> uint64_t {
        // cliente c em [1..nbcd] -> bit (c-1)
        return (uint64_t)1 << (c - 1);
    };

    // fronteira[(no,mask)] -> lista de índices de rótulos não dominados
    // chave compactada: (uint64_t)node em 8 bits + mask shift
    auto key = [&](int node, uint64_t mask) -> uint64_t {
        // node até ~255, mask até 56 bits restantes
        return (mask << 8) | (uint64_t)(node & 0xFF);
    };

    vector<Label> labels;
    labels.reserve(100000);
    deque<int> openq;

    double t0 = max(nd[dep0].a, 0.0);
    Label root{dep0, t0, 0.0, 0.0, 0ULL, -1, true};
    labels.push_back(root);
    openq.push_back(0);

    unordered_map<uint64_t, vector<int>> frontier;
    frontier.reserve(100000);
    frontier[key(dep0, 0ULL)] = {0};

    int best_idx = -1;
    double best_rc = 1e100;

    while (!openq.empty()) {
        int idx = openq.front();
        openq.pop_front();
        if (!labels[idx].active) continue;

        const Label cur = labels[idx]; // cópia (seguro)

        // chegou no depósito final
        if (cur.node == depf) {
            if (cur.cost_mod < best_rc) {
                best_rc = cur.cost_mod;
                best_idx = idx;
            }
            continue;
        }

        // candidatos = clientes não visitados + depósito final
        vector<int> candidates;
        candidates.reserve(nbcd + 1);

        for (int c = 1; c <= nbcd; c++) {
            if ((cur.mask & cliente_mask(c)) == 0ULL) candidates.push_back(c);
        }
        candidates.push_back(depf);

        for (int j : candidates) {
            uint64_t new_mask = cur.mask;
            if (1 <= j && j <= nbcd) new_mask |= cliente_mask(j);

            // capacidade
            double new_load = cur.load;
            if (1 <= j && j <= nbcd) new_load += nd[j].d;
            if (new_load > cap_k) continue;

            // janela de tempo
            double tt = travel_time(cur.node, j);
            double arr = cur.time + nd[cur.node].s + tt;
            if (arr < nd[j].a) arr = nd[j].a;
            if (arr > nd[j].b) continue;

            // custo reduzido
            double cost_mod_new = cur.cost_mod + tt;
            if (1 <= j && j <= nbcd) cost_mod_new -= pi[j - 1];
            if (j == depf) cost_mod_new -= sigma_k;

            // dominância (no,mask)
            uint64_t kkey = key(j, new_mask);
            auto it = frontier.find(kkey);
            if (it == frontier.end()) {
                it = frontier.emplace(kkey, vector<int>{}).first;
            }
            vector<int>& lst = it->second;

            // 1) se alguém domina o novo -> descarta
            bool dominated = false;
            for (int old_idx : lst) {
                if (!labels[old_idx].active) continue;
                const auto& old = labels[old_idx];
                if (domina(old.cost_mod, old.time, old.load,
                          cost_mod_new, arr, new_load)) {
                    dominated = true;
                    break;
                }
            }
            if (dominated) continue;

            // 2) novo domina alguns -> desativa
            vector<int> new_lst;
            new_lst.reserve(lst.size() + 1);
            for (int old_idx : lst) {
                if (!labels[old_idx].active) continue;
                const auto& old = labels[old_idx];
                if (domina(cost_mod_new, arr, new_load,
                          old.cost_mod, old.time, old.load)) {
                    labels[old_idx].active = false;
                } else {
                    new_lst.push_back(old_idx);
                }
            }

            // 3) cria rótulo
            int new_idx = (int)labels.size();
            labels.push_back(Label{j, arr, new_load, cost_mod_new, new_mask, idx, true});
            openq.push_back(new_idx);

            new_lst.push_back(new_idx);
            lst.swap(new_lst);
        }
    }

    if (best_idx < 0 || best_rc >= -1e-6) {
        cout << "NONE\n";
        return 0;
    }

    // reconstrói rota
    vector<int> rev;
    for (int i = best_idx; i != -1; i = labels[i].parent) rev.push_back(labels[i].node);
    reverse(rev.begin(), rev.end());

    // custo real
    double cost_real = 0.0;
    for (size_t i = 0; i + 1 < rev.size(); i++)
        cost_real += travel_time(rev[i], rev[i + 1]);

    // saída fácil de parsear no Python:
    // OK rc cost m v1 v2 ... vm
    cout.setf(std::ios::fixed);
    cout << setprecision(10);
    cout << "OK " << best_rc << " " << cost_real << " " << rev.size();
    for (int v : rev) cout << " " << v;
    cout << "\n";
    return 0;
}
