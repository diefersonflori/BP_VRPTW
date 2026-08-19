# Branch-and-Price for Vehicle Routing and Offshore Logistics

This repository contains the optimization framework developed during my PhD research in Naval and Ocean Engineering at the University of São Paulo (USP).

The project focuses on vehicle routing problems with time windows and on an offshore supply vessel routing problem motivated by Petrobras logistics operations.

## Main topics

- Operations Research
- Vehicle Routing Problem with Time Windows (VRPTW)
- Offshore supply vessel routing
- Mixed-integer optimization
- Dantzig-Wolfe decomposition
- Column generation
- Branch-and-price
- Dual stabilization
- Heuristic and exact pricing

## Solution approach

The main solution method is based on a Dantzig-Wolfe reformulation and column generation.

A branch-and-price framework is used to obtain integer solutions. The pricing problem combines heuristic procedures and exact algorithms, including implementations in C++ for computationally intensive components.

The repository also contains compact formulations used for validation and computational comparison.

## Applications

### Classical VRPTW

The implementation was tested on classical Solomon VRPTW benchmark instances to validate the column-generation and branch-and-price framework.

### Offshore logistics

The framework was extended to an offshore routing problem involving Platform Supply Vessels (PSVs), heterogeneous fleets, operational resources, and multiple service time windows.

Computational experiments include instances based on offshore logistics characteristics and benchmark instances from the literature.

## Technologies

- Python
- C++
- Gurobi
- Mathematical programming
- Git
- Data analysis and computational experimentation

## Repository contents

The repository contains:

- branch-and-price and column-generation implementations;
- heuristic and exact pricing algorithms;
- compact mathematical models used for validation;
- C++ pricing implementations;
- Solomon VRPTW instances;
- offshore and literature-based test instances;
- scripts for instance conversion and validation;
- computational experiment results and analysis files.

Because this repository was also used as the working environment for my PhD research, some folders contain experimental scripts, validation routines, and intermediate computational studies.

## Key implementation highlights

- Branch-and-price framework with column generation for routing problems.
- Dantzig-Wolfe decomposition of the compact formulation.
- Dual stabilization to improve column-generation convergence.
- Heuristic bidirectional pricing followed by exact pricing when required.
- C++ implementation of computationally intensive pricing components.
- Python integration for model management, experiments, and result analysis.
- Gurobi used for mathematical programming and restricted master problems.
- Computational validation on classical Solomon VRPTW benchmarks and offshore routing instances.

## Research context

This work is part of my PhD research in Naval and Ocean Engineering at the University of São Paulo, focused on Operations Research methods for logistics and transportation.

The research investigates exact optimization methods for routing problems, with particular emphasis on branch-and-price, column generation, and offshore supply logistics.

## Author

**Dieferson Flori Massarotto**

Operations Research & Simulation Engineer  
PhD in Naval and Ocean Engineering — University of São Paulo

Research interests: mathematical optimization, routing, simulation, logistics, transportation, and decision-support systems.
