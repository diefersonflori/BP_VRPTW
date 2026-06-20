window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Melhor inteira do pool | rotas ativas: 5",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=0",
      "vehicle": 0,
      "sequence": [
        0,
        32,
        33,
        31,
        35,
        37,
        38,
        39,
        36,
        34,
        51
      ],
      "total_real_cost": 97.0,
      "total_reduced_cost": 97.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 32,
          "x": 10.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 31.0,
          "due_date": 100.0,
          "service_time": 90.0
        },
        {
          "id": 33,
          "x": 8.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 87.0,
          "due_date": 158.0,
          "service_time": 90.0
        },
        {
          "id": 31,
          "x": 10.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 200.0,
          "due_date": 237.0,
          "service_time": 90.0
        },
        {
          "id": 35,
          "x": 5.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 283.0,
          "due_date": 344.0,
          "service_time": 90.0
        },
        {
          "id": 37,
          "x": 2.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 383.0,
          "due_date": 434.0,
          "service_time": 90.0
        },
        {
          "id": 38,
          "x": 0.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 479.0,
          "due_date": 522.0,
          "service_time": 90.0
        },
        {
          "id": 39,
          "x": 0.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 567.0,
          "due_date": 624.0,
          "service_time": 90.0
        },
        {
          "id": 36,
          "x": 5.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 665.0,
          "due_date": 716.0,
          "service_time": 90.0
        },
        {
          "id": 34,
          "x": 8.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 751.0,
          "due_date": 816.0,
          "service_time": 90.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 32,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 10.0,
          "to_y": 40.0,
          "real_cost": 31.6,
          "reduced_cost": 31.6
        },
        {
          "from": 32,
          "to": 33,
          "from_x": 10.0,
          "from_y": 40.0,
          "to_x": 8.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 33,
          "to": 31,
          "from_x": 8.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 35.0,
          "real_cost": 5.3,
          "reduced_cost": 5.3
        },
        {
          "from": 31,
          "to": 35,
          "from_x": 10.0,
          "from_y": 35.0,
          "to_x": 5.0,
          "to_y": 35.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 35,
          "to": 37,
          "from_x": 5.0,
          "from_y": 35.0,
          "to_x": 2.0,
          "to_y": 40.0,
          "real_cost": 5.8,
          "reduced_cost": 5.8
        },
        {
          "from": 37,
          "to": 38,
          "from_x": 2.0,
          "from_y": 40.0,
          "to_x": 0.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 38,
          "to": 39,
          "from_x": 0.0,
          "from_y": 40.0,
          "to_x": 0.0,
          "to_y": 45.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 39,
          "to": 36,
          "from_x": 0.0,
          "from_y": 45.0,
          "to_x": 5.0,
          "to_y": 45.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 36,
          "to": 34,
          "from_x": 5.0,
          "from_y": 45.0,
          "to_x": 8.0,
          "to_y": 45.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 34,
          "to": 51,
          "from_x": 8.0,
          "from_y": 45.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 32.3,
          "reduced_cost": 32.3
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=0",
      "vehicle": 1,
      "sequence": [
        0,
        43,
        42,
        41,
        40,
        44,
        46,
        45,
        48,
        50,
        49,
        47,
        51
      ],
      "total_real_cost": 59.7,
      "total_reduced_cost": 59.7,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 43,
          "x": 33.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 16.0,
          "due_date": 80.0,
          "service_time": 90.0
        },
        {
          "id": 42,
          "x": 33.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 68.0,
          "due_date": 149.0,
          "service_time": 90.0
        },
        {
          "id": 41,
          "x": 35.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 166.0,
          "due_date": 235.0,
          "service_time": 90.0
        },
        {
          "id": 40,
          "x": 35.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 264.0,
          "due_date": 321.0,
          "service_time": 90.0
        },
        {
          "id": 44,
          "x": 32.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 359.0,
          "due_date": 412.0,
          "service_time": 90.0
        },
        {
          "id": 46,
          "x": 30.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 448.0,
          "due_date": 509.0,
          "service_time": 90.0
        },
        {
          "id": 45,
          "x": 30.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 541.0,
          "due_date": 600.0,
          "service_time": 90.0
        },
        {
          "id": 48,
          "x": 28.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 632.0,
          "due_date": 693.0,
          "service_time": 90.0
        },
        {
          "id": 50,
          "x": 26.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 815.0,
          "due_date": 880.0,
          "service_time": 90.0
        },
        {
          "id": 49,
          "x": 28.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 1001.0,
          "due_date": 1066.0,
          "service_time": 90.0
        },
        {
          "id": 47,
          "x": 30.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 1054.0,
          "due_date": 1127.0,
          "service_time": 90.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 43,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 33.0,
          "to_y": 35.0,
          "real_cost": 16.5,
          "reduced_cost": 16.5
        },
        {
          "from": 43,
          "to": 42,
          "from_x": 33.0,
          "from_y": 35.0,
          "to_x": 33.0,
          "to_y": 32.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 42,
          "to": 41,
          "from_x": 33.0,
          "from_y": 32.0,
          "to_x": 35.0,
          "to_y": 32.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 41,
          "to": 40,
          "from_x": 35.0,
          "from_y": 32.0,
          "to_x": 35.0,
          "to_y": 30.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 40,
          "to": 44,
          "from_x": 35.0,
          "from_y": 30.0,
          "to_x": 32.0,
          "to_y": 30.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 44,
          "to": 46,
          "from_x": 32.0,
          "from_y": 30.0,
          "to_x": 30.0,
          "to_y": 32.0,
          "real_cost": 2.8,
          "reduced_cost": 2.8
        },
        {
          "from": 46,
          "to": 45,
          "from_x": 30.0,
          "from_y": 32.0,
          "to_x": 30.0,
          "to_y": 30.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 45,
          "to": 48,
          "from_x": 30.0,
          "from_y": 30.0,
          "to_x": 28.0,
          "to_y": 30.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 48,
          "to": 50,
          "from_x": 28.0,
          "from_y": 30.0,
          "to_x": 26.0,
          "to_y": 32.0,
          "real_cost": 2.8,
          "reduced_cost": 2.8
        },
        {
          "from": 50,
          "to": 49,
          "from_x": 26.0,
          "from_y": 32.0,
          "to_x": 28.0,
          "to_y": 35.0,
          "real_cost": 3.6,
          "reduced_cost": 3.6
        },
        {
          "from": 49,
          "to": 47,
          "from_x": 28.0,
          "from_y": 35.0,
          "to_x": 30.0,
          "to_y": 35.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 47,
          "to": 51,
          "from_x": 30.0,
          "from_y": 35.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 18.0,
          "reduced_cost": 18.0
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=0",
      "vehicle": 2,
      "sequence": [
        0,
        5,
        3,
        7,
        8,
        10,
        11,
        9,
        6,
        4,
        2,
        1,
        51
      ],
      "total_real_cost": 59.2,
      "total_reduced_cost": 59.2,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 5,
          "x": 42.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 15.0,
          "due_date": 67.0,
          "service_time": 90.0
        },
        {
          "id": 3,
          "x": 42.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 65.0,
          "due_date": 146.0,
          "service_time": 90.0
        },
        {
          "id": 7,
          "x": 40.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 170.0,
          "due_date": 225.0,
          "service_time": 90.0
        },
        {
          "id": 8,
          "x": 38.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 255.0,
          "due_date": 324.0,
          "service_time": 90.0
        },
        {
          "id": 10,
          "x": 35.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 357.0,
          "due_date": 410.0,
          "service_time": 90.0
        },
        {
          "id": 11,
          "x": 35.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 448.0,
          "due_date": 505.0,
          "service_time": 90.0
        },
        {
          "id": 9,
          "x": 38.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 534.0,
          "due_date": 605.0,
          "service_time": 90.0
        },
        {
          "id": 6,
          "x": 40.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 621.0,
          "due_date": 702.0,
          "service_time": 90.0
        },
        {
          "id": 4,
          "x": 42.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 727.0,
          "due_date": 782.0,
          "service_time": 90.0
        },
        {
          "id": 2,
          "x": 45.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 825.0,
          "due_date": 870.0,
          "service_time": 90.0
        },
        {
          "id": 1,
          "x": 45.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 912.0,
          "due_date": 967.0,
          "service_time": 90.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 5,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 42.0,
          "to_y": 65.0,
          "real_cost": 15.1,
          "reduced_cost": 15.1
        },
        {
          "from": 5,
          "to": 3,
          "from_x": 42.0,
          "from_y": 65.0,
          "to_x": 42.0,
          "to_y": 66.0,
          "real_cost": 1.0,
          "reduced_cost": 1.0
        },
        {
          "from": 3,
          "to": 7,
          "from_x": 42.0,
          "from_y": 66.0,
          "to_x": 40.0,
          "to_y": 66.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 7,
          "to": 8,
          "from_x": 40.0,
          "from_y": 66.0,
          "to_x": 38.0,
          "to_y": 68.0,
          "real_cost": 2.8,
          "reduced_cost": 2.8
        },
        {
          "from": 8,
          "to": 10,
          "from_x": 38.0,
          "from_y": 68.0,
          "to_x": 35.0,
          "to_y": 66.0,
          "real_cost": 3.6,
          "reduced_cost": 3.6
        },
        {
          "from": 10,
          "to": 11,
          "from_x": 35.0,
          "from_y": 66.0,
          "to_x": 35.0,
          "to_y": 69.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 11,
          "to": 9,
          "from_x": 35.0,
          "from_y": 69.0,
          "to_x": 38.0,
          "to_y": 70.0,
          "real_cost": 3.1,
          "reduced_cost": 3.1
        },
        {
          "from": 9,
          "to": 6,
          "from_x": 38.0,
          "from_y": 70.0,
          "to_x": 40.0,
          "to_y": 69.0,
          "real_cost": 2.2,
          "reduced_cost": 2.2
        },
        {
          "from": 6,
          "to": 4,
          "from_x": 40.0,
          "from_y": 69.0,
          "to_x": 42.0,
          "to_y": 68.0,
          "real_cost": 2.2,
          "reduced_cost": 2.2
        },
        {
          "from": 4,
          "to": 2,
          "from_x": 42.0,
          "from_y": 68.0,
          "to_x": 45.0,
          "to_y": 70.0,
          "real_cost": 3.6,
          "reduced_cost": 3.6
        },
        {
          "from": 2,
          "to": 1,
          "from_x": 45.0,
          "from_y": 70.0,
          "to_x": 45.0,
          "to_y": 68.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 1,
          "to": 51,
          "from_x": 45.0,
          "from_y": 68.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 18.6,
          "reduced_cost": 18.6
        }
      ],
      "color": "#0f766e"
    },
    {
      "id": 3,
      "name": "veic=3 col=0",
      "vehicle": 3,
      "sequence": [
        0,
        13,
        17,
        18,
        19,
        15,
        16,
        14,
        12,
        51
      ],
      "total_real_cost": 95.8,
      "total_reduced_cost": 95.8,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 13,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 30.0,
          "due_date": 92.0,
          "service_time": 90.0
        },
        {
          "id": 17,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 99.0,
          "due_date": 148.0,
          "service_time": 90.0
        },
        {
          "id": 18,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 179.0,
          "due_date": 254.0,
          "service_time": 90.0
        },
        {
          "id": 19,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 278.0,
          "due_date": 345.0,
          "service_time": 90.0
        },
        {
          "id": 15,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 384.0,
          "due_date": 429.0,
          "service_time": 90.0
        },
        {
          "id": 16,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 475.0,
          "due_date": 528.0,
          "service_time": 90.0
        },
        {
          "id": 14,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 567.0,
          "due_date": 620.0,
          "service_time": 90.0
        },
        {
          "id": 12,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 652.0,
          "due_date": 721.0,
          "service_time": 90.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 13,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 30.8,
          "reduced_cost": 30.8
        },
        {
          "from": 13,
          "to": 17,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 4.0,
          "reduced_cost": 4.0
        },
        {
          "from": 17,
          "to": 18,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 18,
          "to": 19,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 19,
          "to": 15,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 15,
          "to": 16,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 16,
          "to": 14,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 14,
          "to": 12,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 12,
          "to": 51,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 38.0,
          "reduced_cost": 38.0
        }
      ],
      "color": "#7c3aed"
    },
    {
      "id": 4,
      "name": "veic=4 col=0",
      "vehicle": 4,
      "sequence": [
        0,
        20,
        24,
        25,
        27,
        29,
        30,
        28,
        26,
        23,
        22,
        21,
        51
      ],
      "total_real_cost": 50.7,
      "total_reduced_cost": 50.7,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        },
        {
          "id": 20,
          "x": 30.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 10.0,
          "due_date": 73.0,
          "service_time": 90.0
        },
        {
          "id": 24,
          "x": 25.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 65.0,
          "due_date": 144.0,
          "service_time": 90.0
        },
        {
          "id": 25,
          "x": 25.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 169.0,
          "due_date": 224.0,
          "service_time": 90.0
        },
        {
          "id": 27,
          "x": 23.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 261.0,
          "due_date": 316.0,
          "service_time": 90.0
        },
        {
          "id": 29,
          "x": 20.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 358.0,
          "due_date": 405.0,
          "service_time": 90.0
        },
        {
          "id": 30,
          "x": 20.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 449.0,
          "due_date": 504.0,
          "service_time": 90.0
        },
        {
          "id": 28,
          "x": 23.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 546.0,
          "due_date": 593.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 25.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 622.0,
          "due_date": 701.0,
          "service_time": 90.0
        },
        {
          "id": 23,
          "x": 28.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 732.0,
          "due_date": 777.0,
          "service_time": 90.0
        },
        {
          "id": 22,
          "x": 28.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 812.0,
          "due_date": 883.0,
          "service_time": 90.0
        },
        {
          "id": 21,
          "x": 30.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 914.0,
          "due_date": 965.0,
          "service_time": 90.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 1236.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 20,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 30.0,
          "to_y": 50.0,
          "real_cost": 10.0,
          "reduced_cost": 10.0
        },
        {
          "from": 20,
          "to": 24,
          "from_x": 30.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 50.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 24,
          "to": 25,
          "from_x": 25.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 25,
          "to": 27,
          "from_x": 25.0,
          "from_y": 52.0,
          "to_x": 23.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 27,
          "to": 29,
          "from_x": 23.0,
          "from_y": 52.0,
          "to_x": 20.0,
          "to_y": 50.0,
          "real_cost": 3.6,
          "reduced_cost": 3.6
        },
        {
          "from": 29,
          "to": 30,
          "from_x": 20.0,
          "from_y": 50.0,
          "to_x": 20.0,
          "to_y": 55.0,
          "real_cost": 5.0,
          "reduced_cost": 5.0
        },
        {
          "from": 30,
          "to": 28,
          "from_x": 20.0,
          "from_y": 55.0,
          "to_x": 23.0,
          "to_y": 55.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 28,
          "to": 26,
          "from_x": 23.0,
          "from_y": 55.0,
          "to_x": 25.0,
          "to_y": 55.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 26,
          "to": 23,
          "from_x": 25.0,
          "from_y": 55.0,
          "to_x": 28.0,
          "to_y": 55.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 23,
          "to": 22,
          "from_x": 28.0,
          "from_y": 55.0,
          "to_x": 28.0,
          "to_y": 52.0,
          "real_cost": 3.0,
          "reduced_cost": 3.0
        },
        {
          "from": 22,
          "to": 21,
          "from_x": 28.0,
          "from_y": 52.0,
          "to_x": 30.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": 2.0
        },
        {
          "from": 21,
          "to": 51,
          "from_x": 30.0,
          "from_y": 52.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 10.1,
          "reduced_cost": 10.1
        }
      ],
      "color": "#ea580c"
    }
  ]
};
