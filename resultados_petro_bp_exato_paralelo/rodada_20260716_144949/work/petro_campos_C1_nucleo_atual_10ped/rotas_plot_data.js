window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Melhor inteira do pool | rotas ativas: 3",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=2",
      "vehicle": 0,
      "sequence": [
        0,
        1,
        2,
        3,
        4,
        9,
        10,
        5,
        6,
        7,
        8,
        11
      ],
      "total_real_cost": 72577.0,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_start",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        },
        {
          "id": 1,
          "x": -40.528,
          "y": -22.573,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 3600.0
        },
        {
          "id": 2,
          "x": -40.528,
          "y": -22.573,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 1800.0
        },
        {
          "id": 3,
          "x": -40.528,
          "y": -22.573,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 19183.0
        },
        {
          "id": 4,
          "x": -40.528,
          "y": -22.573,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 1200.0
        },
        {
          "id": 9,
          "x": -40.25944889,
          "y": -22.55011,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 24000.0
        },
        {
          "id": 10,
          "x": -40.25944889,
          "y": -22.55011,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 313200.0,
          "service_time": 9600.0
        },
        {
          "id": 5,
          "x": -40.123,
          "y": -22.561,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 453600.0,
          "service_time": 1200.0
        },
        {
          "id": 6,
          "x": -40.123,
          "y": -22.561,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 453600.0,
          "service_time": 6600.0
        },
        {
          "id": 7,
          "x": -40.123,
          "y": -22.561,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 453600.0,
          "service_time": 8880.0
        },
        {
          "id": 8,
          "x": -40.123,
          "y": -22.561,
          "kind": "customer",
          "ready_time": 216000.0,
          "due_date": 453600.0,
          "service_time": 16154.0
        },
        {
          "id": 11,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_end",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 1,
          "from_x": -40.996652,
          "from_y": -21.845602,
          "to_x": -40.528,
          "to_y": -22.573,
          "real_cost": 24013.0,
          "reduced_cost": 14013.0
        },
        {
          "from": 1,
          "to": 2,
          "from_x": -40.528,
          "from_y": -22.573,
          "to_x": -40.528,
          "to_y": -22.573,
          "real_cost": 0.0,
          "reduced_cost": -10000.0
        },
        {
          "from": 2,
          "to": 3,
          "from_x": -40.528,
          "from_y": -22.573,
          "to_x": -40.528,
          "to_y": -22.573,
          "real_cost": 0.0,
          "reduced_cost": -10000.0
        },
        {
          "from": 3,
          "to": 4,
          "from_x": -40.528,
          "from_y": -22.573,
          "to_x": -40.528,
          "to_y": -22.573,
          "real_cost": 0.0,
          "reduced_cost": -10000.0
        },
        {
          "from": 4,
          "to": 9,
          "from_x": -40.528,
          "from_y": -22.573,
          "to_x": -40.25944889,
          "to_y": -22.55011,
          "real_cost": 11489.0,
          "reduced_cost": 5189.0
        },
        {
          "from": 9,
          "to": 10,
          "from_x": -40.25944889,
          "from_y": -22.55011,
          "to_x": -40.25944889,
          "to_y": -22.55011,
          "real_cost": 0.0,
          "reduced_cost": 0.0
        },
        {
          "from": 10,
          "to": 5,
          "from_x": -40.25944889,
          "from_y": -22.55011,
          "to_x": -40.123,
          "to_y": -22.561,
          "real_cost": 9305.0,
          "reduced_cost": -695.0
        },
        {
          "from": 5,
          "to": 6,
          "from_x": -40.123,
          "from_y": -22.561,
          "to_x": -40.123,
          "to_y": -22.561,
          "real_cost": 0.0,
          "reduced_cost": -10000.0
        },
        {
          "from": 6,
          "to": 7,
          "from_x": -40.123,
          "from_y": -22.561,
          "to_x": -40.123,
          "to_y": -22.561,
          "real_cost": 0.0,
          "reduced_cost": -6277.0
        },
        {
          "from": 7,
          "to": 8,
          "from_x": -40.123,
          "from_y": -22.561,
          "to_x": -40.123,
          "to_y": -22.561,
          "real_cost": 0.0,
          "reduced_cost": 0.0
        },
        {
          "from": 8,
          "to": 11,
          "from_x": -40.123,
          "from_y": -22.561,
          "to_x": -40.996652,
          "to_y": -21.845602,
          "real_cost": 27770.0,
          "reduced_cost": 27770.0
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=1",
      "vehicle": 1,
      "sequence": [
        0,
        11
      ],
      "total_real_cost": 0.0,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_start",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        },
        {
          "id": 11,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_end",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 11,
          "from_x": -40.996652,
          "from_y": -21.845602,
          "to_x": -40.996652,
          "to_y": -21.845602,
          "real_cost": 0.0,
          "reduced_cost": 0.0
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=1",
      "vehicle": 2,
      "sequence": [
        0,
        11
      ],
      "total_real_cost": 0.0,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_start",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        },
        {
          "id": 11,
          "x": -40.996652,
          "y": -21.845602,
          "kind": "depot_end",
          "ready_time": 10800.0,
          "due_date": 604800.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 11,
          "from_x": -40.996652,
          "from_y": -21.845602,
          "to_x": -40.996652,
          "to_y": -21.845602,
          "real_cost": 0.0,
          "reduced_cost": 0.0
        }
      ],
      "color": "#0f766e"
    }
  ]
};
