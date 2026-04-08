window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 18",
  "subtitle": "Melhor inteira do pool | rotas ativas: 5",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=307",
      "vehicle": 0,
      "sequence": [
        0,
        14,
        16,
        6,
        13,
        26
      ],
      "total_real_cost": 79.2,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        },
        {
          "id": 14,
          "x": 15.0,
          "y": 10.0,
          "kind": "customer",
          "ready_time": 32.0,
          "due_date": 62.0,
          "service_time": 10.0
        },
        {
          "id": 16,
          "x": 10.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 65.0,
          "due_date": 95.0,
          "service_time": 10.0
        },
        {
          "id": 6,
          "x": 25.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 89.0,
          "due_date": 119.0,
          "service_time": 10.0
        },
        {
          "id": 13,
          "x": 30.0,
          "y": 25.0,
          "kind": "customer",
          "ready_time": 149.0,
          "due_date": 179.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 14,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 15.0,
          "to_y": 10.0,
          "real_cost": 32.0,
          "reduced_cost": 32.0
        },
        {
          "from": 14,
          "to": 16,
          "from_x": 15.0,
          "from_y": 10.0,
          "to_x": 10.0,
          "to_y": 20.0,
          "real_cost": 11.1,
          "reduced_cost": 1.6
        },
        {
          "from": 16,
          "to": 6,
          "from_x": 10.0,
          "from_y": 20.0,
          "to_x": 25.0,
          "to_y": 30.0,
          "real_cost": 18.0,
          "reduced_cost": 4.0
        },
        {
          "from": 6,
          "to": 13,
          "from_x": 25.0,
          "from_y": 30.0,
          "to_x": 30.0,
          "to_y": 25.0,
          "real_cost": 7.0,
          "reduced_cost": -8.2
        },
        {
          "from": 13,
          "to": 26,
          "from_x": 30.0,
          "from_y": 25.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 11.1,
          "reduced_cost": 11.1
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=326",
      "vehicle": 1,
      "sequence": [
        0,
        7,
        19,
        11,
        10,
        26
      ],
      "total_real_cost": 75.8,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        },
        {
          "id": 7,
          "x": 20.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 198.0,
          "service_time": 10.0
        },
        {
          "id": 19,
          "x": 15.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 66.0,
          "due_date": 96.0,
          "service_time": 10.0
        },
        {
          "id": 11,
          "x": 20.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 57.0,
          "due_date": 87.0,
          "service_time": 10.0
        },
        {
          "id": 10,
          "x": 30.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 114.0,
          "due_date": 144.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 7,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 20.0,
          "to_y": 50.0,
          "real_cost": 21.2,
          "reduced_cost": 18.5
        },
        {
          "from": 7,
          "to": 19,
          "from_x": 20.0,
          "from_y": 50.0,
          "to_x": 15.0,
          "to_y": 60.0,
          "real_cost": 11.1,
          "reduced_cost": 5.9
        },
        {
          "from": 19,
          "to": 11,
          "from_x": 15.0,
          "from_y": 60.0,
          "to_x": 20.0,
          "to_y": 65.0,
          "real_cost": 7.0,
          "reduced_cost": -35.2
        },
        {
          "from": 11,
          "to": 10,
          "from_x": 20.0,
          "from_y": 65.0,
          "to_x": 30.0,
          "to_y": 60.0,
          "real_cost": 11.1,
          "reduced_cost": -14.6
        },
        {
          "from": 10,
          "to": 26,
          "from_x": 30.0,
          "from_y": 60.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 25.4,
          "reduced_cost": 25.4
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=243",
      "vehicle": 2,
      "sequence": [
        0,
        18,
        8,
        17,
        5,
        26
      ],
      "total_real_cost": 70.7,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        },
        {
          "id": 18,
          "x": 20.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 77.0,
          "due_date": 107.0,
          "service_time": 10.0
        },
        {
          "id": 8,
          "x": 10.0,
          "y": 43.0,
          "kind": "customer",
          "ready_time": 85.0,
          "due_date": 115.0,
          "service_time": 10.0
        },
        {
          "id": 17,
          "x": 5.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 147.0,
          "due_date": 177.0,
          "service_time": 10.0
        },
        {
          "id": 5,
          "x": 15.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 199.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 18,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 20.0,
          "to_y": 40.0,
          "real_cost": 15.8,
          "reduced_cost": 0.4
        },
        {
          "from": 18,
          "to": 8,
          "from_x": 20.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 43.0,
          "real_cost": 10.4,
          "reduced_cost": -10.1
        },
        {
          "from": 8,
          "to": 17,
          "from_x": 10.0,
          "from_y": 43.0,
          "to_x": 5.0,
          "to_y": 30.0,
          "real_cost": 13.9,
          "reduced_cost": -17.8
        },
        {
          "from": 17,
          "to": 5,
          "from_x": 5.0,
          "from_y": 30.0,
          "to_x": 15.0,
          "to_y": 30.0,
          "real_cost": 10.0,
          "reduced_cost": 6.9
        },
        {
          "from": 5,
          "to": 26,
          "from_x": 15.0,
          "from_y": 30.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 20.6,
          "reduced_cost": 20.6
        }
      ],
      "color": "#0f766e"
    },
    {
      "id": 3,
      "name": "veic=3 col=311",
      "vehicle": 3,
      "sequence": [
        0,
        2,
        15,
        23,
        22,
        4,
        25,
        21,
        26
      ],
      "total_real_cost": 129.2,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        },
        {
          "id": 2,
          "x": 35.0,
          "y": 17.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 202.0,
          "service_time": 10.0
        },
        {
          "id": 15,
          "x": 30.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 51.0,
          "due_date": 81.0,
          "service_time": 10.0
        },
        {
          "id": 23,
          "x": 55.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 58.0,
          "due_date": 88.0,
          "service_time": 10.0
        },
        {
          "id": 22,
          "x": 45.0,
          "y": 10.0,
          "kind": "customer",
          "ready_time": 87.0,
          "due_date": 117.0,
          "service_time": 10.0
        },
        {
          "id": 4,
          "x": 55.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 139.0,
          "due_date": 169.0,
          "service_time": 10.0
        },
        {
          "id": 25,
          "x": 65.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 156.0,
          "due_date": 186.0,
          "service_time": 10.0
        },
        {
          "id": 21,
          "x": 45.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 201.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 2,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 35.0,
          "to_y": 17.0,
          "real_cost": 18.0,
          "reduced_cost": 7.6
        },
        {
          "from": 2,
          "to": 15,
          "from_x": 35.0,
          "from_y": 17.0,
          "to_x": 30.0,
          "to_y": 5.0,
          "real_cost": 13.0,
          "reduced_cost": -2.2
        },
        {
          "from": 15,
          "to": 23,
          "from_x": 30.0,
          "from_y": 5.0,
          "to_x": 55.0,
          "to_y": 5.0,
          "real_cost": 25.0,
          "reduced_cost": -10.9
        },
        {
          "from": 23,
          "to": 22,
          "from_x": 55.0,
          "from_y": 5.0,
          "to_x": 45.0,
          "to_y": 10.0,
          "real_cost": 11.1,
          "reduced_cost": 0.9
        },
        {
          "from": 22,
          "to": 4,
          "from_x": 45.0,
          "from_y": 10.0,
          "to_x": 55.0,
          "to_y": 20.0,
          "real_cost": 14.1,
          "reduced_cost": -10.2
        },
        {
          "from": 4,
          "to": 25,
          "from_x": 55.0,
          "from_y": 20.0,
          "to_x": 65.0,
          "to_y": 20.0,
          "real_cost": 10.0,
          "reduced_cost": -17.6
        },
        {
          "from": 25,
          "to": 21,
          "from_x": 65.0,
          "from_y": 20.0,
          "to_x": 45.0,
          "to_y": 20.0,
          "real_cost": 20.0,
          "reduced_cost": 14.4
        },
        {
          "from": 21,
          "to": 26,
          "from_x": 45.0,
          "from_y": 20.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 18.0,
          "reduced_cost": 18.0
        }
      ],
      "color": "#7c3aed"
    },
    {
      "id": 4,
      "name": "veic=4 col=387",
      "vehicle": 4,
      "sequence": [
        0,
        1,
        9,
        20,
        3,
        24,
        12,
        26
      ],
      "total_real_cost": 110.5,
      "total_reduced_cost": 8.1,
      "nodes": [
        {
          "id": 0,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        },
        {
          "id": 1,
          "x": 41.0,
          "y": 49.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 204.0,
          "service_time": 10.0
        },
        {
          "id": 9,
          "x": 55.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 87.0,
          "due_date": 117.0,
          "service_time": 10.0
        },
        {
          "id": 20,
          "x": 45.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 116.0,
          "due_date": 146.0,
          "service_time": 10.0
        },
        {
          "id": 3,
          "x": 55.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 197.0,
          "service_time": 10.0
        },
        {
          "id": 24,
          "x": 65.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 143.0,
          "due_date": 173.0,
          "service_time": 10.0
        },
        {
          "id": 12,
          "x": 50.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 205.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 35.0,
          "y": 35.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 230.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 1,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 41.0,
          "to_y": 49.0,
          "real_cost": 15.2,
          "reduced_cost": 9.9
        },
        {
          "from": 1,
          "to": 9,
          "from_x": 41.0,
          "from_y": 49.0,
          "to_x": 55.0,
          "to_y": 60.0,
          "real_cost": 17.8,
          "reduced_cost": -19.2
        },
        {
          "from": 9,
          "to": 20,
          "from_x": 55.0,
          "from_y": 60.0,
          "to_x": 45.0,
          "to_y": 65.0,
          "real_cost": 11.1,
          "reduced_cost": -5.6
        },
        {
          "from": 20,
          "to": 3,
          "from_x": 45.0,
          "from_y": 65.0,
          "to_x": 55.0,
          "to_y": 45.0,
          "real_cost": 22.3,
          "reduced_cost": 12.1
        },
        {
          "from": 3,
          "to": 24,
          "from_x": 55.0,
          "from_y": 45.0,
          "to_x": 65.0,
          "to_y": 35.0,
          "real_cost": 14.1,
          "reduced_cost": -15.3
        },
        {
          "from": 24,
          "to": 12,
          "from_x": 65.0,
          "from_y": 35.0,
          "to_x": 50.0,
          "to_y": 35.0,
          "real_cost": 15.0,
          "reduced_cost": 11.2
        },
        {
          "from": 12,
          "to": 26,
          "from_x": 50.0,
          "from_y": 35.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 15.0,
          "reduced_cost": 15.0
        }
      ],
      "color": "#ea580c"
    }
  ]
};
