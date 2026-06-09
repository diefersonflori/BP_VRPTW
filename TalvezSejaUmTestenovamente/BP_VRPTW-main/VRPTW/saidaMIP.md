import sys; print('Python %s on %s' % (sys.version, sys.platform))
C:\Users\Investigador\anaconda3\python.exe "C:/Program Files/JetBrains/PyCharm 2025.2.4/plugins/python-ce/helpers/pydev/pydevd.py" --multiprocess --qt-support=auto --client 127.0.0.1 --port 60940 --file C:\Users\Investigador\Documents\VRPTW\main.py 
Connected to: <socket.socket fd=1056, family=2, type=1, proto=0, laddr=('127.0.0.1', 60941), raddr=('127.0.0.1', 60940)>.
Connected to pydev debugger (build 252.27397.106)
==================== Iniciando a resolução do modelo exato
Set parameter Username
Set parameter LicenseID to value 2727320
Academic license - for non-commercial use only - expires 2026-10-24
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 346 rows, 198 columns and 1306 nonzeros
Model fingerprint: 0xc63a090d
Variable types: 36 continuous, 162 integer (162 binary)
Coefficient statistics:
  Matrix range     [1e+00, 1e+05]
  Objective range  [9e-01, 5e+00]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+05]
Presolve removed 90 rows and 40 columns
Presolve time: 0.00s
Presolved: 256 rows, 158 columns, 2223 nonzeros
Variable types: 30 continuous, 128 integer (128 binary)
Root relaxation: objective 1.113515e+01, 48 iterations, 0.00 seconds (0.00 work units)
    Nodes    |    Current Node    |     Objective Bounds      |     Work
 Expl Unexpl |  Obj  Depth IntInf | Incumbent    BestBd   Gap | It/Node Time
     0     0   11.13515    0   14          -   11.13515      -     -    0s
H    0     0                      21.3191740   11.13515  47.8%     -    0s
     0     0   11.96833    0   14   21.31917   11.96833  43.9%     -    0s
     0     0   12.49403    0   21   21.31917   12.49403  41.4%     -    0s
H    0     0                      19.5780344   12.49403  36.2%     -    0s
H    0     0                      18.6572246   12.49403  33.0%     -    0s
H    0     0                      17.5742282   12.49403  28.9%     -    0s
H    0     0                      16.0122442   12.78442  20.2%     -    0s
     0     0   12.79522    0   21   16.01224   12.79522  20.1%     -    0s
     0     0   13.03704    0   21   16.01224   13.03704  18.6%     -    0s
     0     0   13.03704    0   21   16.01224   13.03704  18.6%     -    0s
     0     2   13.03704    0   21   16.01224   13.03704  18.6%     -    0s
H   32    49                      14.7568630   13.03704  11.7%  10.2    0s
Cutting planes:
  Learned: 3
  Gomory: 2
  Cover: 1
  Implied bound: 4
  MIR: 11
  StrongCG: 5
  RLT: 9
  Relax-and-lift: 1
Explored 319 nodes (2451 simplex iterations) in 0.09 seconds (0.07 work units)
Thread count was 12 (of 12 available processors)
Solution count 6: 14.7569 16.0122 17.5742 ... 21.3192
Optimal solution found (tolerance 1.00e-04)
Best objective 1.475686300025e+01, best bound 1.475686300025e+01, gap 0.0000%
== Veículo 0 ==
Rota: 0 -> 7 -> 5 -> 6 -> 8
  Nó |  Chegada |    Saída |  Carga_in | Carga_out
   0 |     0.00 |     0.00 |      0.00 |       5.0
   7 |     2.12 |    12.12 |      5.00 |      31.0
   5 |    14.18 |    24.18 |     31.00 |      34.0
   6 |    25.18 |    35.18 |     34.00 |       0.0
   8 |  9916.86 |  9916.86 |      0.00 |         -
== Veículo 1 ==
Rota: 0 -> 1 -> 3 -> 4 -> 2 -> 8
  Nó |  Chegada |    Saída |  Carga_in | Carga_out
   0 |     0.00 |     0.00 |      0.00 |      10.0
   1 |     1.38 |    11.38 |     10.00 |      23.0
   3 |    12.71 |    22.71 |     23.00 |      42.0
   4 |    24.98 |    34.98 |     42.00 |      49.0
   2 |    36.82 |    46.82 |     49.00 |       0.0
   8 |  9999.00 |  9999.00 |      0.00 |         -
Solução encontrada com sucesso!
x[0][0][7] = 1
x[0][5][6] = 1
x[0][6][8] = 1
x[0][7][5] = 1
x[1][0][1] = 1
x[1][1][3] = 1
x[1][2][8] = 1
x[1][3][4] = 1
x[1][4][2] = 1
✅ Solução exportada com sucesso para 'solucao_ex.json'
========Geracao de Colunas==========
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 40 columns and 168 nonzeros
Model fingerprint: 0x34d0e282
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
Presolve removed 0 rows and 4 columns
Presolve time: 0.00s
Presolved: 9 rows, 36 columns, 158 nonzeros
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    6.5782436e+00   5.000000e+00   0.000000e+00      0s
      12    1.8652363e+01   0.000000e+00   0.000000e+00      0s
Solved in 12 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.865236303e+01
%%%%%%%%%%%%%%%%% iteracao 1
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 18.6524
--- Colunas Escolhidas na Solução do Mestre (Iteração 0) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 0.2500
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
  Veículo 0, Rota 6:
    - Valor (lambda): 0.2500
    - Sequência: [0, 5, 2, 1, 3, 4, 8]
    - Custo:     14.16
  Veículo 0, Rota 15:
    - Valor (lambda): 0.2500
    - Sequência: [0, 3, 6, 4, 1, 7, 8]
    - Custo:     16.20
SOL itera k 1
  Veículo 1, Rota 3:
    - Valor (lambda): 0.5000
    - Sequência: [0, 2, 5, 7, 1, 6, 8]
    - Custo:     10.86
  Veículo 1, Rota 4:
    - Valor (lambda): 0.5000
    - Sequência: [0, 3, 4, 8]
    - Custo:     6.58
Custo Total do Mestre (Lower Bound) nesta iteração: 18.6524
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 4, 3, 1, 7, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 6, 7, 1, 3, 4, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 42 columns and 180 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -8.7745920e+30   3.250000e+30   8.774592e+00      0s
       9    1.7098927e+01   0.000000e+00   0.000000e+00      0s
Solved in 9 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.709892739e+01
%%%%%%%%%%%%%%%%% iteracao 3
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 17.0989
--- Colunas Escolhidas na Solução do Mestre (Iteração 1) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 0.5000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
  Veículo 0, Rota 6:
    - Valor (lambda): 0.5000
    - Sequência: [0, 5, 2, 1, 3, 4, 8]
    - Custo:     14.16
SOL itera k 1
  Veículo 1, Rota 20:
    - Valor (lambda): 0.5000
    - Sequência: [0, 6, 7, 1, 3, 4, 8]
    - Custo:     10.67
Custo Total do Mestre (Lower Bound) nesta iteração: 17.0989
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 2, 4, 3, 1, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 2, 4, 3, 1, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 44 columns and 190 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -4.2493115e+30   6.000000e+30   4.249312e+00      0s
       4    1.6544487e+01   0.000000e+00   0.000000e+00      0s
Solved in 4 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.654448653e+01
%%%%%%%%%%%%%%%%% iteracao 5
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.5445
--- Colunas Escolhidas na Solução do Mestre (Iteração 2) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 0.5000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
  Veículo 0, Rota 21:
    - Valor (lambda): 0.5000
    - Sequência: [0, 2, 4, 3, 1, 8]
    - Custo:     9.30
SOL itera k 1
  Veículo 1, Rota 14:
    - Valor (lambda): 0.5000
    - Sequência: [0, 5, 8]
    - Custo:     3.75
  Veículo 1, Rota 20:
    - Valor (lambda): 0.5000
    - Sequência: [0, 6, 7, 1, 3, 4, 8]
    - Custo:     10.67
Custo Total do Mestre (Lower Bound) nesta iteração: 16.5445
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 5, 6, 4, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 5, 6, 4, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 46 columns and 198 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -5.3041081e+30   5.000000e+30   5.304108e+00      0s
       2    1.6544487e+01   0.000000e+00   0.000000e+00      0s
Solved in 2 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.654448653e+01
%%%%%%%%%%%%%%%%% iteracao 7
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.5445
--- Colunas Escolhidas na Solução do Mestre (Iteração 3) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 0.5000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
  Veículo 0, Rota 21:
    - Valor (lambda): 0.5000
    - Sequência: [0, 2, 4, 3, 1, 8]
    - Custo:     9.30
SOL itera k 1
  Veículo 1, Rota 14:
    - Valor (lambda): 0.5000
    - Sequência: [0, 5, 8]
    - Custo:     3.75
  Veículo 1, Rota 20:
    - Valor (lambda): 0.5000
    - Sequência: [0, 6, 7, 1, 3, 4, 8]
    - Custo:     10.67
/n/n/n-------- PRIMEIRO MIP------------
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 46 columns and 198 nonzeros
Model fingerprint: 0x980722d9
Variable types: 0 continuous, 46 integer (46 binary)
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
Presolve removed 9 rows and 46 columns
Presolve time: 0.00s
Presolve: All rows and columns removed
Explored 0 nodes (0 simplex iterations) in 0.00 seconds (0.00 work units)
Thread count was 1 (of 12 available processors)
Solution count 1: 20.3272 
Optimal solution found (tolerance 1.00e-04)
Best objective 2.032718342366e+01, best bound 2.032718342366e+01, gap 0.0000%
--- Detalhes das Rotas Escolhidas (Solução Inteira-MIP 1) ---
  Veículo 0, Rota 2:
    - Sequência: [0, 7, 3, 8]
    - Custo:     7.89
  Veículo 1, Rota 17:
    - Sequência: [0, 5, 6, 2, 1, 4, 8]
    - Custo:     12.43
✅ Solução GC exportada com sucesso para 'solucao_gc.json'
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 46 columns and 198 nonzeros
Model fingerprint: 0x7e115d26
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
Presolve removed 0 rows and 5 columns
Presolve time: 0.00s
Presolved: 9 rows, 41 columns, 182 nonzeros
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    6.5782436e+00   5.000000e+00   0.000000e+00      0s
      10    1.6544487e+01   0.000000e+00   0.000000e+00      0s
Solved in 10 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.654448653e+01
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 6 vezes
(0,7,0) -> usado 4 vezes
(2,8,0) -> usado 4 vezes
(3,4,1) -> usado 4 vezes
(4,8,1) -> usado 4 vezes
===========================================
Selecionando aleatoriamente o arco (0,7,0) para fixar em 1 (usado 4 vezes).
Restrição adicionada: veículo 0 deve ter pelo menos uma rota contendo o arco 0->7.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 10 rows, 46 columns and 202 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6544487e+01   5.000000e-01   0.000000e+00      0s
       6    1.8194422e+01   0.000000e+00   0.000000e+00      0s
Solved in 6 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.819442219e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 18.1944
Custo Total do Mestre (Lower Bound) nesta iteração: 16.5445
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl5.729297595744353
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 1, 3, 4, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 1, 3, 4, 6, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 10 rows, 48 columns and 213 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -1.9099387e+30   4.000000e+30   1.909939e+00      0s
       5    1.7557776e+01   0.000000e+00   0.000000e+00      0s
Solved in 5 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.755777595e+01
%%%%%%%%%%%%%%%%% iteracao 9
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 17.5578
--- Colunas Escolhidas na Solução do Mestre (Iteração 4) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 0.6667
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
  Veículo 0, Rota 17:
    - Valor (lambda): 0.3333
    - Sequência: [0, 7, 8]
    - Custo:     4.24
SOL itera k 1
  Veículo 1, Rota 5:
    - Valor (lambda): 0.3333
    - Sequência: [0, 1, 5, 4, 3, 8]
    - Custo:     12.37
  Veículo 1, Rota 21:
    - Valor (lambda): 0.3333
    - Sequência: [0, 2, 4, 3, 1, 8]
    - Custo:     8.46
  Veículo 1, Rota 23:
    - Valor (lambda): 0.3333
    - Sequência: [0, 1, 3, 4, 6, 8]
    - Custo:     8.87
Custo Total do Mestre (Lower Bound) nesta iteração: 17.5578
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.4440042001824374
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 1, 3, 4, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 10 rows, 50 columns and 221 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -1.2926426e+30   3.333333e+30   1.292643e+00      0s
       3    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 3 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 11
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 5) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl1.8651791527020842
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 1, 4, 8]
inicia   roda sub probl do veic 1
sub _ k1
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 6, 5, 7, 1, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 10 rows, 52 columns and 230 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -1.4696279e+30   1.800000e+31   1.469628e+00      0s
       2    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 2 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 13
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 6) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 9 vezes
(2,8,0) -> usado 7 vezes
(3,4,1) -> usado 7 vezes
(6,5,0) -> usado 7 vezes
(7,6,0) -> usado 7 vezes
===========================================
Selecionando aleatoriamente o arco (3,4,1) para fixar em 1 (usado 7 vezes).
Restrição adicionada: veículo 1 deve ter pelo menos uma rota contendo o arco 3->4.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 11 rows, 52 columns and 234 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 11 rows, 53 columns and 238 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 15
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 7) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 10 vezes
(2,8,0) -> usado 8 vezes
(6,5,0) -> usado 8 vezes
(7,6,0) -> usado 8 vezes
(1,3,1) -> usado 7 vezes
===========================================
Selecionando aleatoriamente o arco (7,6,0) para fixar em 1 (usado 8 vezes).
Restrição adicionada: veículo 0 deve ter pelo menos uma rota contendo o arco 7->6.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 12 rows, 53 columns and 242 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 12 rows, 54 columns and 246 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 17
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 8) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 11 vezes
(2,8,0) -> usado 9 vezes
(6,5,0) -> usado 9 vezes
(1,3,1) -> usado 8 vezes
(4,8,1) -> usado 8 vezes
===========================================
Selecionando aleatoriamente o arco (6,5,0) para fixar em 1 (usado 9 vezes).
Restrição adicionada: veículo 0 deve ter pelo menos uma rota contendo o arco 6->5.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 13 rows, 54 columns and 247 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 13 rows, 55 columns and 251 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 19
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 9) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 12 vezes
(2,8,0) -> usado 10 vezes
(1,3,1) -> usado 9 vezes
(4,8,1) -> usado 9 vezes
(0,1,1) -> usado 7 vezes
===========================================
Selecionando aleatoriamente o arco (0,1,1) para fixar em 1 (usado 7 vezes).
Restrição adicionada: veículo 1 deve ter pelo menos uma rota contendo o arco 0->1.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 14 rows, 55 columns and 257 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 14 rows, 56 columns and 261 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 21
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 10) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 13 vezes
(2,8,0) -> usado 11 vezes
(1,3,1) -> usado 10 vezes
(4,8,1) -> usado 10 vezes
(7,1,1) -> usado 4 vezes
===========================================
Selecionando aleatoriamente o arco (4,8,1) para fixar em 1 (usado 10 vezes).
Restrição adicionada: veículo 1 deve ter pelo menos uma rota contendo o arco 4->8.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 15 rows, 56 columns and 268 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 15 rows, 57 columns and 272 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 23
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 11) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(5,2,0) -> usado 14 vezes
(2,8,0) -> usado 12 vezes
(1,3,1) -> usado 11 vezes
(7,1,1) -> usado 4 vezes
(0,6,1) -> usado 3 vezes
===========================================
Selecionando aleatoriamente o arco (5,2,0) para fixar em 1 (usado 14 vezes).
Restrição adicionada: veículo 0 deve ter pelo menos uma rota contendo o arco 5->2.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 16 rows, 57 columns and 275 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 16 rows, 58 columns and 279 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 25
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 12) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(2,8,0) -> usado 13 vezes
(1,3,1) -> usado 12 vezes
(7,1,1) -> usado 4 vezes
(0,6,1) -> usado 3 vezes
(6,7,1) -> usado 3 vezes
===========================================
Selecionando aleatoriamente o arco (2,8,0) para fixar em 1 (usado 13 vezes).
Restrição adicionada: veículo 0 deve ter pelo menos uma rota contendo o arco 2->8.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 17 rows, 58 columns and 284 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.01 seconds (0.00 work units)
Optimal objective  1.662204215e+01
--- Solução Ótima Encontrada NO GC HEURISTICO ---
Valor da Função Objetivo (Custo Total): 16.6220
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.5140483659739274
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 5, 6, 8]
inicia   roda sub probl do veic 1
sub _ k1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 17 rows, 59 columns and 288 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   0.000000e+00   0.000000e+00      0s
Solved in 0 iterations and 0.00 seconds (0.00 work units)
Optimal objective  1.662204215e+01
%%%%%%%%%%%%%%%%% iteracao 27
--- Solução Ótima Encontrada NO GC MESTRE ---
Valor da Função Objetivo (Custo Total): 16.6220
--- Colunas Escolhidas na Solução do Mestre (Iteração 13) ---
SOL itera k 0
  Veículo 0, Rota 0:
    - Valor (lambda): 1.0000
    - Sequência: [0, 7, 6, 5, 2, 8]
    - Custo:     9.37
SOL itera k 1
  Veículo 1, Rota 24:
    - Valor (lambda): 1.0000
    - Sequência: [0, 1, 3, 4, 8]
    - Custo:     7.25
ITERACAO SEM MELHORA
===== TOP 5 ARCOS (i,j,k) MAIS USADOS =====
(1,3,1) -> usado 13 vezes
(7,1,1) -> usado 4 vezes
(0,6,1) -> usado 3 vezes
(6,7,1) -> usado 3 vezes
(0,2,0) -> usado 2 vezes
===========================================
Selecionando aleatoriamente o arco (0,6,1) para fixar em 1 (usado 3 vezes).
Restrição adicionada: veículo 1 deve ter pelo menos uma rota contendo o arco 0->6.
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 18 rows, 59 columns and 290 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0    1.6622042e+01   1.000000e+00   0.000000e+00      0s
Solved in 3 iterations and 0.00 seconds (0.00 work units)
Infeasible model
--- Modelo mestre não encontrou solução ótima após fixação ---
Custo Total do Mestre (Lower Bound) nesta iteração: 16.6220
--- Fim da Listagem de Colunas ---
inicia   roda sub probl do veic 0
sub _ k0
duadddddl2.7608254045424303
duadddddl0.6023265897491044
Terminou roda sub probl do veic 0
NOVA ROTA ADICIONADA veiculo 0
[0, 7, 1, 3, 4, 8]
inicia   roda sub probl do veic 1
sub _ k1
duadddddl1.8788051637991776
duadddddl0.7829244969130684
Terminou roda sub probl do veic 1
NOVA ROTA ADICIONADA veiculo 1
[0, 6, 1, 3, 4, 8]
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 18 rows, 61 columns and 300 nonzeros
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
LP warm-start: use basis
Iteration    Objective       Primal Inf.    Dual Inf.      Time
       0   -3.9945869e+29   3.500000e+30   3.994587e-01      0s
Solved in 2 iterations and 0.00 seconds (0.00 work units)
Infeasible model
%%%%%%%%%%%%%%%%% iteracao 29
Problema mestre não resolvido/ótimo. Parando.
/n/n/n-------- INICIOU MIP------------
🧹 Removendo restrições de arco fixado antes do MIP final...
✔️ Removida: arco_fixado_6_5_0
✔️ Removida: arco_fixado_0_7_0
✔️ Removida: arco_fixado_4_8_1
✔️ Removida: arco_fixado_0_6_1
✔️ Removida: arco_fixado_7_6_0
✔️ Removida: arco_fixado_3_4_1
✔️ Removida: arco_fixado_5_2_0
✔️ Removida: arco_fixado_2_8_0
✔️ Removida: arco_fixado_0_1_1
Gurobi Optimizer version 12.0.3 build v12.0.3rc0 (win64 - Windows 11.0 (22631.2))
CPU model: 12th Gen Intel(R) Core(TM) i7-1255U, instruction set [SSE2|AVX|AVX2]
Thread count: 10 physical cores, 12 logical processors, using up to 12 threads
Optimize a model with 9 rows, 61 columns and 264 nonzeros
Model fingerprint: 0x00b000f5
Variable types: 0 continuous, 61 integer (61 binary)
Coefficient statistics:
  Matrix range     [1e+00, 1e+00]
  Objective range  [3e+00, 2e+01]
  Bounds range     [1e+00, 1e+00]
  RHS range        [1e+00, 1e+00]
MIP start from previous solve produced solution with objective 20.3272 (0.00s)
Loaded MIP start from previous solve with objective 20.3272
Presolve removed 9 rows and 61 columns
Presolve time: 0.00s
Presolve: All rows and columns removed
Explored 0 nodes (0 simplex iterations) in 0.00 seconds (0.00 work units)
Thread count was 1 (of 12 available processors)
Solution count 2: 14.7569 20.3272 
Optimal solution found (tolerance 1.00e-04)
Best objective 1.475686300025e+01, best bound 1.475686300025e+01, gap 0.0000%
==== SOLUÇÃO ÓTIMA INTEIRA ENCONTRADA ====
Custo Total Inteiro (Upper Bound): 14.7569
--- Detalhes das Rotas Escolhidas (Solução Inteira) ---
  Veículo 0, Rota 28:
    - Sequência: [0, 7, 5, 6, 8]
    - Custo:     6.30
  Veículo 1, Rota 21:
    - Sequência: [0, 2, 4, 3, 1, 8]
    - Custo:     8.46
==============================================
[[[0, 0], [0, 11], [2, 2], [1, 1], [0, 0], [2, 2], [0, 3], [15, 0], [0, 0]], [[0, 0], [0, 0], [0, 0], [2, 13], [0, 0], [0, 1], [0, 1], [1, 0], [2, 1]], [[0, 0], [2, 0], [0, 0], [0, 0], [2, 1], [0, 1], [0, 0], [0, 0], [14, 0]], [[0, 0], [2, 1], [0, 0], [0, 0], [2, 14], [0, 0], [1, 0], [0, 0], [0, 1]], [[0, 0], [1, 0], [0, 0], [2, 2], [0, 0], [0, 0], [0, 1], [0, 0], [2, 13]], [[0, 0], [0, 0], [16, 0], [0, 0], [0, 1], [0, 0], [0, 0], [0, 1], [0, 2]], [[0, 0], [0, 0], [0, 0], [0, 0], [1, 0], [14, 0], [0, 0], [0, 3], [0, 2]], [[0, 0], [0, 4], [0, 0], [0, 0], [0, 0], [0, 0], [14, 0], [0, 0], [2, 0]], [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]]]
✅ Solução GC exportada com sucesso para 'solucao_gcm.json'
