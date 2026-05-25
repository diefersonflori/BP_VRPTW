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
        20,
        24,
        27,
        25,
        29,
        30,
        28,
        22,
        26,
        23,
        21,
        47,
        51
      ],
      "total_real_cost": 84.7,
      "total_reduced_cost": 1.585047,
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
          "due_date": 370.0,
          "service_time": 90.0
        },
        {
          "id": 24,
          "x": 25.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 15.0,
          "due_date": 375.0,
          "service_time": 90.0
        },
        {
          "id": 27,
          "x": 23.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 109.0,
          "due_date": 469.0,
          "service_time": 90.0
        },
        {
          "id": 25,
          "x": 25.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 17.0,
          "due_date": 377.0,
          "service_time": 90.0
        },
        {
          "id": 29,
          "x": 20.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 202.0,
          "due_date": 562.0,
          "service_time": 90.0
        },
        {
          "id": 30,
          "x": 20.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 297.0,
          "due_date": 657.0,
          "service_time": 90.0
        },
        {
          "id": 28,
          "x": 23.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 390.0,
          "due_date": 750.0,
          "service_time": 90.0
        },
        {
          "id": 22,
          "x": 28.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 668.0,
          "due_date": 1028.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 25.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 482.0,
          "due_date": 842.0,
          "service_time": 90.0
        },
        {
          "id": 23,
          "x": 28.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 575.0,
          "due_date": 935.0,
          "service_time": 90.0
        },
        {
          "id": 21,
          "x": 30.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 760.0,
          "due_date": 1120.0,
          "service_time": 90.0
        },
        {
          "id": 47,
          "x": 30.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 767.0,
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
          "to": 20,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 30.0,
          "to_y": 50.0,
          "real_cost": 10.0,
          "reduced_cost": 16.048263
        },
        {
          "from": 20,
          "to": 24,
          "from_x": 30.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 50.0,
          "real_cost": 5.0,
          "reduced_cost": -7.867795
        },
        {
          "from": 24,
          "to": 27,
          "from_x": 25.0,
          "from_y": 50.0,
          "to_x": 23.0,
          "to_y": 52.0,
          "real_cost": 2.8,
          "reduced_cost": -4.396102
        },
        {
          "from": 27,
          "to": 25,
          "from_x": 23.0,
          "from_y": 52.0,
          "to_x": 25.0,
          "to_y": 52.0,
          "real_cost": 2.0,
          "reduced_cost": -18.609738
        },
        {
          "from": 25,
          "to": 29,
          "from_x": 25.0,
          "from_y": 52.0,
          "to_x": 20.0,
          "to_y": 50.0,
          "real_cost": 5.3,
          "reduced_cost": 0.078995
        },
        {
          "from": 29,
          "to": 30,
          "from_x": 20.0,
          "from_y": 50.0,
          "to_x": 20.0,
          "to_y": 55.0,
          "real_cost": 5.0,
          "reduced_cost": -25.713645
        },
        {
          "from": 30,
          "to": 28,
          "from_x": 20.0,
          "from_y": 55.0,
          "to_x": 23.0,
          "to_y": 55.0,
          "real_cost": 3.0,
          "reduced_cost": -7.241502
        },
        {
          "from": 28,
          "to": 22,
          "from_x": 23.0,
          "from_y": 55.0,
          "to_x": 28.0,
          "to_y": 52.0,
          "real_cost": 5.8,
          "reduced_cost": 14.9564
        },
        {
          "from": 22,
          "to": 26,
          "from_x": 28.0,
          "from_y": 52.0,
          "to_x": 25.0,
          "to_y": 55.0,
          "real_cost": 4.2,
          "reduced_cost": 6.009799
        },
        {
          "from": 26,
          "to": 23,
          "from_x": 25.0,
          "from_y": 55.0,
          "to_x": 28.0,
          "to_y": 55.0,
          "real_cost": 3.0,
          "reduced_cost": -4.145525
        },
        {
          "from": 23,
          "to": 21,
          "from_x": 28.0,
          "from_y": 55.0,
          "to_x": 30.0,
          "to_y": 52.0,
          "real_cost": 3.6,
          "reduced_cost": 7.179027
        },
        {
          "from": 21,
          "to": 47,
          "from_x": 30.0,
          "from_y": 52.0,
          "to_x": 30.0,
          "to_y": 35.0,
          "real_cost": 17.0,
          "reduced_cost": 5.3496
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
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=0",
      "vehicle": 1,
      "sequence": [
        0,
        7,
        8,
        3,
        5,
        10,
        11,
        4,
        9,
        6,
        2,
        1,
        49,
        51
      ],
      "total_real_cost": 111.1,
      "total_reduced_cost": 29.239589,
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
          "id": 7,
          "x": 40.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 18.0,
          "due_date": 378.0,
          "service_time": 90.0
        },
        {
          "id": 8,
          "x": 38.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 110.0,
          "due_date": 470.0,
          "service_time": 90.0
        },
        {
          "id": 3,
          "x": 42.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 16.0,
          "due_date": 376.0,
          "service_time": 90.0
        },
        {
          "id": 5,
          "x": 42.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 15.0,
          "due_date": 375.0,
          "service_time": 90.0
        },
        {
          "id": 10,
          "x": 35.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 204.0,
          "due_date": 564.0,
          "service_time": 90.0
        },
        {
          "id": 11,
          "x": 35.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 297.0,
          "due_date": 657.0,
          "service_time": 90.0
        },
        {
          "id": 4,
          "x": 42.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 575.0,
          "due_date": 935.0,
          "service_time": 90.0
        },
        {
          "id": 9,
          "x": 38.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 390.0,
          "due_date": 750.0,
          "service_time": 90.0
        },
        {
          "id": 6,
          "x": 40.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 482.0,
          "due_date": 842.0,
          "service_time": 90.0
        },
        {
          "id": 2,
          "x": 45.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 668.0,
          "due_date": 1028.0,
          "service_time": 90.0
        },
        {
          "id": 1,
          "x": 45.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 760.0,
          "due_date": 1120.0,
          "service_time": 90.0
        },
        {
          "id": 49,
          "x": 28.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 766.0,
          "due_date": 1126.0,
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
          "to": 7,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 40.0,
          "to_y": 66.0,
          "real_cost": 16.0,
          "reduced_cost": 7.303148
        },
        {
          "from": 7,
          "to": 8,
          "from_x": 40.0,
          "from_y": 66.0,
          "to_x": 38.0,
          "to_y": 68.0,
          "real_cost": 2.8,
          "reduced_cost": -4.362905
        },
        {
          "from": 8,
          "to": 3,
          "from_x": 38.0,
          "from_y": 68.0,
          "to_x": 42.0,
          "to_y": 66.0,
          "real_cost": 4.4,
          "reduced_cost": 1.173382
        },
        {
          "from": 3,
          "to": 5,
          "from_x": 42.0,
          "from_y": 66.0,
          "to_x": 42.0,
          "to_y": 65.0,
          "real_cost": 1.0,
          "reduced_cost": -14.841673
        },
        {
          "from": 5,
          "to": 10,
          "from_x": 42.0,
          "from_y": 65.0,
          "to_x": 35.0,
          "to_y": 66.0,
          "real_cost": 7.0,
          "reduced_cost": -6.972127
        },
        {
          "from": 10,
          "to": 11,
          "from_x": 35.0,
          "from_y": 66.0,
          "to_x": 35.0,
          "to_y": 69.0,
          "real_cost": 3.0,
          "reduced_cost": -25.521698
        },
        {
          "from": 11,
          "to": 4,
          "from_x": 35.0,
          "from_y": 69.0,
          "to_x": 42.0,
          "to_y": 68.0,
          "real_cost": 7.0,
          "reduced_cost": 3.63192
        },
        {
          "from": 4,
          "to": 9,
          "from_x": 42.0,
          "from_y": 68.0,
          "to_x": 38.0,
          "to_y": 70.0,
          "real_cost": 4.4,
          "reduced_cost": 4.609319
        },
        {
          "from": 9,
          "to": 6,
          "from_x": 38.0,
          "from_y": 70.0,
          "to_x": 40.0,
          "to_y": 69.0,
          "real_cost": 2.2,
          "reduced_cost": -7.62628
        },
        {
          "from": 6,
          "to": 2,
          "from_x": 40.0,
          "from_y": 69.0,
          "to_x": 45.0,
          "to_y": 70.0,
          "real_cost": 5.0,
          "reduced_cost": 24.319618
        },
        {
          "from": 2,
          "to": 1,
          "from_x": 45.0,
          "from_y": 70.0,
          "to_x": 45.0,
          "to_y": 68.0,
          "real_cost": 2.0,
          "reduced_cost": -5.274937
        },
        {
          "from": 1,
          "to": 49,
          "from_x": 45.0,
          "from_y": 68.0,
          "to_x": 28.0,
          "to_y": 35.0,
          "real_cost": 37.1,
          "reduced_cost": 31.664553
        },
        {
          "from": 49,
          "to": 51,
          "from_x": 28.0,
          "from_y": 35.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 19.2,
          "reduced_cost": 19.2
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
        41,
        40,
        42,
        43,
        44,
        45,
        46,
        48,
        50,
        34,
        51
      ],
      "total_real_cost": 95.5,
      "total_reduced_cost": 0.0,
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
          "id": 41,
          "x": 35.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 21.0,
          "due_date": 381.0,
          "service_time": 90.0
        },
        {
          "id": 40,
          "x": 35.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 113.0,
          "due_date": 473.0,
          "service_time": 90.0
        },
        {
          "id": 42,
          "x": 33.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 19.0,
          "due_date": 379.0,
          "service_time": 90.0
        },
        {
          "id": 43,
          "x": 33.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 16.0,
          "due_date": 376.0,
          "service_time": 90.0
        },
        {
          "id": 44,
          "x": 32.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 206.0,
          "due_date": 566.0,
          "service_time": 90.0
        },
        {
          "id": 45,
          "x": 30.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 391.0,
          "due_date": 751.0,
          "service_time": 90.0
        },
        {
          "id": 46,
          "x": 30.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 299.0,
          "due_date": 659.0,
          "service_time": 90.0
        },
        {
          "id": 48,
          "x": 28.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 483.0,
          "due_date": 843.0,
          "service_time": 90.0
        },
        {
          "id": 50,
          "x": 26.0,
          "y": 32.0,
          "kind": "customer",
          "ready_time": 668.0,
          "due_date": 1028.0,
          "service_time": 90.0
        },
        {
          "id": 34,
          "x": 8.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 604.0,
          "due_date": 964.0,
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
          "to": 41,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 35.0,
          "to_y": 32.0,
          "real_cost": 18.6,
          "reduced_cost": 3.471378
        },
        {
          "from": 41,
          "to": 40,
          "from_x": 35.0,
          "from_y": 32.0,
          "to_x": 35.0,
          "to_y": 30.0,
          "real_cost": 2.0,
          "reduced_cost": -10.324295
        },
        {
          "from": 40,
          "to": 42,
          "from_x": 35.0,
          "from_y": 30.0,
          "to_x": 33.0,
          "to_y": 32.0,
          "real_cost": 2.8,
          "reduced_cost": 15.06476
        },
        {
          "from": 42,
          "to": 43,
          "from_x": 33.0,
          "from_y": 32.0,
          "to_x": 33.0,
          "to_y": 35.0,
          "real_cost": 3.0,
          "reduced_cost": -3.419019
        },
        {
          "from": 43,
          "to": 44,
          "from_x": 33.0,
          "from_y": 35.0,
          "to_x": 32.0,
          "to_y": 30.0,
          "real_cost": 5.0,
          "reduced_cost": -14.772612
        },
        {
          "from": 44,
          "to": 45,
          "from_x": 32.0,
          "from_y": 30.0,
          "to_x": 30.0,
          "to_y": 30.0,
          "real_cost": 2.0,
          "reduced_cost": 4.362951
        },
        {
          "from": 45,
          "to": 46,
          "from_x": 30.0,
          "from_y": 30.0,
          "to_x": 30.0,
          "to_y": 32.0,
          "real_cost": 2.0,
          "reduced_cost": -20.87104
        },
        {
          "from": 46,
          "to": 48,
          "from_x": 30.0,
          "from_y": 32.0,
          "to_x": 28.0,
          "to_y": 30.0,
          "real_cost": 2.8,
          "reduced_cost": 7.531095
        },
        {
          "from": 48,
          "to": 50,
          "from_x": 28.0,
          "from_y": 30.0,
          "to_x": 26.0,
          "to_y": 32.0,
          "real_cost": 2.8,
          "reduced_cost": -2.198974
        },
        {
          "from": 50,
          "to": 34,
          "from_x": 26.0,
          "from_y": 32.0,
          "to_x": 8.0,
          "to_y": 45.0,
          "real_cost": 22.2,
          "reduced_cost": -13.081515
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
      "color": "#0f766e"
    },
    {
      "id": 3,
      "name": "veic=3 col=0",
      "vehicle": 3,
      "sequence": [
        0,
        18,
        17,
        15,
        13,
        19,
        16,
        14,
        12,
        36,
        51
      ],
      "total_real_cost": 149.5,
      "total_reduced_cost": 0.0,
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
          "id": 18,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 37.0,
          "due_date": 397.0,
          "service_time": 90.0
        },
        {
          "id": 17,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 33.0,
          "due_date": 393.0,
          "service_time": 90.0
        },
        {
          "id": 15,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 227.0,
          "due_date": 587.0,
          "service_time": 90.0
        },
        {
          "id": 13,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 30.0,
          "due_date": 390.0,
          "service_time": 90.0
        },
        {
          "id": 19,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 132.0,
          "due_date": 492.0,
          "service_time": 90.0
        },
        {
          "id": 16,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 322.0,
          "due_date": 682.0,
          "service_time": 90.0
        },
        {
          "id": 14,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 414.0,
          "due_date": 774.0,
          "service_time": 90.0
        },
        {
          "id": 12,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 507.0,
          "due_date": 867.0,
          "service_time": 90.0
        },
        {
          "id": 36,
          "x": 5.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 511.0,
          "due_date": 871.0,
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
          "to": 18,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 35.3,
          "reduced_cost": 21.832564
        },
        {
          "from": 18,
          "to": 17,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 3.0,
          "reduced_cost": -18.008502
        },
        {
          "from": 17,
          "to": 15,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.3,
          "reduced_cost": -10.881303
        },
        {
          "from": 15,
          "to": 13,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 5.3,
          "reduced_cost": -21.69575
        },
        {
          "from": 13,
          "to": 19,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 8.6,
          "reduced_cost": -4.599197
        },
        {
          "from": 19,
          "to": 16,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 7.0,
          "reduced_cost": 5.700369
        },
        {
          "from": 16,
          "to": 14,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 2.0,
          "reduced_cost": -18.390004
        },
        {
          "from": 14,
          "to": 12,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": -27.528991
        },
        {
          "from": 12,
          "to": 36,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 5.0,
          "to_y": 45.0,
          "real_cost": 44.7,
          "reduced_cost": 36.333544
        },
        {
          "from": 36,
          "to": 51,
          "from_x": 5.0,
          "from_y": 45.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 35.3,
          "reduced_cost": 35.3
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
        31,
        35,
        33,
        32,
        38,
        37,
        39,
        51
      ],
      "total_real_cost": 103.9,
      "total_reduced_cost": 0.0,
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
          "id": 31,
          "x": 10.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 39.0,
          "due_date": 399.0,
          "service_time": 90.0
        },
        {
          "id": 35,
          "x": 5.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 134.0,
          "due_date": 494.0,
          "service_time": 90.0
        },
        {
          "id": 33,
          "x": 8.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 33.0,
          "due_date": 393.0,
          "service_time": 90.0
        },
        {
          "id": 32,
          "x": 10.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 31.0,
          "due_date": 391.0,
          "service_time": 90.0
        },
        {
          "id": 38,
          "x": 0.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 321.0,
          "due_date": 681.0,
          "service_time": 90.0
        },
        {
          "id": 37,
          "x": 2.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 229.0,
          "due_date": 589.0,
          "service_time": 90.0
        },
        {
          "id": 39,
          "x": 0.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 416.0,
          "due_date": 776.0,
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
          "to": 31,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 10.0,
          "to_y": 35.0,
          "real_cost": 33.5,
          "reduced_cost": 8.308421
        },
        {
          "from": 31,
          "to": 35,
          "from_x": 10.0,
          "from_y": 35.0,
          "to_x": 5.0,
          "to_y": 35.0,
          "real_cost": 5.0,
          "reduced_cost": -11.416532
        },
        {
          "from": 35,
          "to": 33,
          "from_x": 5.0,
          "from_y": 35.0,
          "to_x": 8.0,
          "to_y": 40.0,
          "real_cost": 5.8,
          "reduced_cost": -21.01942
        },
        {
          "from": 33,
          "to": 32,
          "from_x": 8.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": 3.580301
        },
        {
          "from": 32,
          "to": 38,
          "from_x": 10.0,
          "from_y": 40.0,
          "to_x": 0.0,
          "to_y": 40.0,
          "real_cost": 10.0,
          "reduced_cost": -16.364976
        },
        {
          "from": 38,
          "to": 37,
          "from_x": 0.0,
          "from_y": 40.0,
          "to_x": 2.0,
          "to_y": 40.0,
          "real_cost": 2.0,
          "reduced_cost": -18.637557
        },
        {
          "from": 37,
          "to": 39,
          "from_x": 2.0,
          "from_y": 40.0,
          "to_x": 0.0,
          "to_y": 45.0,
          "real_cost": 5.3,
          "reduced_cost": 13.312493
        },
        {
          "from": 39,
          "to": 51,
          "from_x": 0.0,
          "from_y": 45.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 40.3,
          "reduced_cost": 40.3
        }
      ],
      "color": "#ea580c"
    }
  ]
};
