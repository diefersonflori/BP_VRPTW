window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 0",
  "subtitle": "Melhor inteira do pool | rotas ativas: 8",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=0",
      "vehicle": 0,
      "sequence": [
        0,
        37,
        42,
        14,
        44,
        16,
        6,
        51
      ],
      "total_real_cost": 80.0,
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
          "id": 37,
          "x": 20.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 198.0,
          "service_time": 10.0
        },
        {
          "id": 42,
          "x": 24.0,
          "y": 12.0,
          "kind": "customer",
          "ready_time": 25.0,
          "due_date": 55.0,
          "service_time": 10.0
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
          "id": 44,
          "x": 11.0,
          "y": 14.0,
          "kind": "customer",
          "ready_time": 59.0,
          "due_date": 89.0,
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
          "id": 51,
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
          "to": 37,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 20.0,
          "to_y": 20.0,
          "real_cost": 21.2,
          "reduced_cost": 968.153923
        },
        {
          "from": 37,
          "to": 42,
          "from_x": 20.0,
          "from_y": 20.0,
          "to_x": 24.0,
          "to_y": 12.0,
          "real_cost": 8.9,
          "reduced_cost": 4213.673174
        },
        {
          "from": 42,
          "to": 14,
          "from_x": 24.0,
          "from_y": 12.0,
          "to_x": 15.0,
          "to_y": 10.0,
          "real_cost": 9.2,
          "reduced_cost": 10073.173849
        },
        {
          "from": 14,
          "to": 44,
          "from_x": 15.0,
          "from_y": 10.0,
          "to_x": 11.0,
          "to_y": 14.0,
          "real_cost": 5.6,
          "reduced_cost": -9992.126433
        },
        {
          "from": 44,
          "to": 16,
          "from_x": 11.0,
          "from_y": 14.0,
          "to_x": 10.0,
          "to_y": 20.0,
          "real_cost": 6.0,
          "reduced_cost": -9930.026151
        },
        {
          "from": 16,
          "to": 6,
          "from_x": 10.0,
          "from_y": 20.0,
          "to_x": 25.0,
          "to_y": 30.0,
          "real_cost": 18.0,
          "reduced_cost": -1514.352679
        },
        {
          "from": 6,
          "to": 51,
          "from_x": 25.0,
          "from_y": 30.0,
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
      "name": "veic=1 col=0",
      "vehicle": 1,
      "sequence": [
        0,
        2,
        15,
        38,
        43,
        13,
        51
      ],
      "total_real_cost": 108.2,
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
          "id": 38,
          "x": 5.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 73.0,
          "due_date": 103.0,
          "service_time": 10.0
        },
        {
          "id": 43,
          "x": 23.0,
          "y": 3.0,
          "kind": "customer",
          "ready_time": 122.0,
          "due_date": 152.0,
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
          "id": 51,
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
          "reduced_cost": 2319.695446
        },
        {
          "from": 2,
          "to": 15,
          "from_x": 35.0,
          "from_y": 17.0,
          "to_x": 30.0,
          "to_y": 5.0,
          "real_cost": 13.0,
          "reduced_cost": -9935.070397
        },
        {
          "from": 15,
          "to": 38,
          "from_x": 30.0,
          "from_y": 5.0,
          "to_x": 5.0,
          "to_y": 5.0,
          "real_cost": 25.0,
          "reduced_cost": -9911.026151
        },
        {
          "from": 38,
          "to": 43,
          "from_x": 5.0,
          "from_y": 5.0,
          "to_x": 23.0,
          "to_y": 3.0,
          "real_cost": 18.1,
          "reduced_cost": 10077.495478
        },
        {
          "from": 43,
          "to": 13,
          "from_x": 23.0,
          "from_y": 3.0,
          "to_x": 30.0,
          "to_y": 25.0,
          "real_cost": 23.0,
          "reduced_cost": 1267.401308
        },
        {
          "from": 13,
          "to": 51,
          "from_x": 30.0,
          "from_y": 25.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 11.1,
          "reduced_cost": 11.1
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
        21,
        39,
        23,
        40,
        24,
        12,
        51
      ],
      "total_real_cost": 125.5,
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
          "id": 21,
          "x": 45.0,
          "y": 20.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 201.0,
          "service_time": 10.0
        },
        {
          "id": 39,
          "x": 60.0,
          "y": 12.0,
          "kind": "customer",
          "ready_time": 34.0,
          "due_date": 64.0,
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
          "id": 40,
          "x": 40.0,
          "y": 25.0,
          "kind": "customer",
          "ready_time": 75.0,
          "due_date": 105.0,
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
          "id": 51,
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
          "to": 21,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 45.0,
          "to_y": 20.0,
          "real_cost": 18.0,
          "reduced_cost": 785.783409
        },
        {
          "from": 21,
          "to": 39,
          "from_x": 45.0,
          "from_y": 20.0,
          "to_x": 60.0,
          "to_y": 12.0,
          "real_cost": 17.0,
          "reduced_cost": -9919.026151
        },
        {
          "from": 39,
          "to": 23,
          "from_x": 60.0,
          "from_y": 12.0,
          "to_x": 55.0,
          "to_y": 5.0,
          "real_cost": 8.6,
          "reduced_cost": -9979.207868
        },
        {
          "from": 23,
          "to": 40,
          "from_x": 55.0,
          "from_y": 5.0,
          "to_x": 40.0,
          "to_y": 25.0,
          "real_cost": 25.0,
          "reduced_cost": -2710.497999
        },
        {
          "from": 40,
          "to": 24,
          "from_x": 40.0,
          "from_y": 25.0,
          "to_x": 65.0,
          "to_y": 35.0,
          "real_cost": 26.9,
          "reduced_cost": 10090.873849
        },
        {
          "from": 24,
          "to": 12,
          "from_x": 65.0,
          "from_y": 35.0,
          "to_x": 50.0,
          "to_y": 35.0,
          "real_cost": 15.0,
          "reduced_cost": 5546.670444
        },
        {
          "from": 12,
          "to": 51,
          "from_x": 50.0,
          "from_y": 35.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 15.0,
          "reduced_cost": 15.0
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
        29,
        22,
        41,
        4,
        25,
        26,
        51
      ],
      "total_real_cost": 132.9,
      "total_reduced_cost": -0.0,
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
          "id": 29,
          "x": 64.0,
          "y": 42.0,
          "kind": "customer",
          "ready_time": 53.0,
          "due_date": 83.0,
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
          "id": 41,
          "x": 42.0,
          "y": 7.0,
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
          "id": 26,
          "x": 45.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 208.0,
          "service_time": 10.0
        },
        {
          "id": 51,
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
          "to": 29,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 64.0,
          "to_y": 42.0,
          "real_cost": 29.8,
          "reduced_cost": -9921.917966
        },
        {
          "from": 29,
          "to": 22,
          "from_x": 64.0,
          "from_y": 42.0,
          "to_x": 45.0,
          "to_y": 10.0,
          "real_cost": 37.2,
          "reduced_cost": 5789.565909
        },
        {
          "from": 22,
          "to": 41,
          "from_x": 45.0,
          "from_y": 10.0,
          "to_x": 42.0,
          "to_y": 7.0,
          "real_cost": 4.2,
          "reduced_cost": -7390.420768
        },
        {
          "from": 41,
          "to": 4,
          "from_x": 42.0,
          "from_y": 7.0,
          "to_x": 55.0,
          "to_y": 20.0,
          "real_cost": 18.3,
          "reduced_cost": -485.344944
        },
        {
          "from": 4,
          "to": 25,
          "from_x": 55.0,
          "from_y": 20.0,
          "to_x": 65.0,
          "to_y": 20.0,
          "real_cost": 10.0,
          "reduced_cost": 2998.000109
        },
        {
          "from": 25,
          "to": 26,
          "from_x": 65.0,
          "from_y": 20.0,
          "to_x": 45.0,
          "to_y": 30.0,
          "real_cost": 22.3,
          "reduced_cost": 2828.613345
        },
        {
          "from": 26,
          "to": 51,
          "from_x": 45.0,
          "from_y": 30.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 11.1,
          "reduced_cost": 11.1
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
        50,
        33,
        30,
        9,
        35,
        34,
        3,
        51
      ],
      "total_real_cost": 110.8,
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
          "id": 50,
          "x": 47.0,
          "y": 47.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 203.0,
          "service_time": 10.0
        },
        {
          "id": 33,
          "x": 53.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 27.0,
          "due_date": 57.0,
          "service_time": 10.0
        },
        {
          "id": 30,
          "x": 40.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 61.0,
          "due_date": 91.0,
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
          "id": 35,
          "x": 63.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 133.0,
          "due_date": 163.0,
          "service_time": 10.0
        },
        {
          "id": 34,
          "x": 65.0,
          "y": 55.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 183.0,
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
          "id": 51,
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
          "to": 50,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 47.0,
          "to_y": 47.0,
          "real_cost": 16.9,
          "reduced_cost": 10078.46435
        },
        {
          "from": 50,
          "to": 33,
          "from_x": 47.0,
          "from_y": 47.0,
          "to_x": 53.0,
          "to_y": 52.0,
          "real_cost": 7.8,
          "reduced_cost": -7470.42441
        },
        {
          "from": 33,
          "to": 30,
          "from_x": 53.0,
          "from_y": 52.0,
          "to_x": 40.0,
          "to_y": 60.0,
          "real_cost": 15.2,
          "reduced_cost": -9952.32814
        },
        {
          "from": 30,
          "to": 9,
          "from_x": 40.0,
          "from_y": 60.0,
          "to_x": 55.0,
          "to_y": 60.0,
          "real_cost": 15.0,
          "reduced_cost": -3654.630857
        },
        {
          "from": 9,
          "to": 35,
          "from_x": 55.0,
          "from_y": 60.0,
          "to_x": 63.0,
          "to_y": 65.0,
          "real_cost": 9.4,
          "reduced_cost": 6951.778488
        },
        {
          "from": 35,
          "to": 34,
          "from_x": 63.0,
          "from_y": 65.0,
          "to_x": 65.0,
          "to_y": 55.0,
          "real_cost": 10.1,
          "reduced_cost": 1310.28686
        },
        {
          "from": 34,
          "to": 3,
          "from_x": 65.0,
          "from_y": 55.0,
          "to_x": 55.0,
          "to_y": 45.0,
          "real_cost": 14.1,
          "reduced_cost": -3455.850606
        },
        {
          "from": 3,
          "to": 51,
          "from_x": 55.0,
          "from_y": 45.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 22.3,
          "reduced_cost": 22.3
        }
      ],
      "color": "#ea580c"
    },
    {
      "id": 5,
      "name": "veic=5 col=0",
      "vehicle": 5,
      "sequence": [
        0,
        28,
        27,
        18,
        8,
        7,
        31,
        51
      ],
      "total_real_cost": 79.1,
      "total_reduced_cost": -0.0,
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
          "id": 28,
          "x": 41.0,
          "y": 37.0,
          "kind": "customer",
          "ready_time": 29.0,
          "due_date": 59.0,
          "service_time": 10.0
        },
        {
          "id": 27,
          "x": 35.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 27.0,
          "due_date": 57.0,
          "service_time": 10.0
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
          "id": 7,
          "x": 20.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 198.0,
          "service_time": 10.0
        },
        {
          "id": 31,
          "x": 31.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 202.0,
          "service_time": 10.0
        },
        {
          "id": 51,
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
          "to": 28,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 41.0,
          "to_y": 37.0,
          "real_cost": 6.3,
          "reduced_cost": -1766.435096
        },
        {
          "from": 28,
          "to": 27,
          "from_x": 41.0,
          "from_y": 37.0,
          "to_x": 35.0,
          "to_y": 40.0,
          "real_cost": 6.7,
          "reduced_cost": -2959.172706
        },
        {
          "from": 27,
          "to": 18,
          "from_x": 35.0,
          "from_y": 40.0,
          "to_x": 20.0,
          "to_y": 40.0,
          "real_cost": 15.0,
          "reduced_cost": -2667.814262
        },
        {
          "from": 18,
          "to": 8,
          "from_x": 20.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 43.0,
          "real_cost": 10.4,
          "reduced_cost": -9935.225488
        },
        {
          "from": 8,
          "to": 7,
          "from_x": 10.0,
          "from_y": 43.0,
          "to_x": 20.0,
          "to_y": 50.0,
          "real_cost": 12.2,
          "reduced_cost": 1070.008535
        },
        {
          "from": 7,
          "to": 31,
          "from_x": 20.0,
          "from_y": 50.0,
          "to_x": 31.0,
          "to_y": 52.0,
          "real_cost": 11.1,
          "reduced_cost": 10070.834701
        },
        {
          "from": 31,
          "to": 51,
          "from_x": 31.0,
          "from_y": 52.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 17.4,
          "reduced_cost": 17.4
        }
      ],
      "color": "#0891b2"
    },
    {
      "id": 6,
      "name": "veic=6 col=0",
      "vehicle": 6,
      "sequence": [
        0,
        48,
        47,
        19,
        11,
        10,
        20,
        32,
        1,
        51
      ],
      "total_real_cost": 122.8,
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
          "id": 48,
          "x": 13.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 192.0,
          "service_time": 10.0
        },
        {
          "id": 47,
          "x": 8.0,
          "y": 56.0,
          "kind": "customer",
          "ready_time": 41.0,
          "due_date": 71.0,
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
          "id": 20,
          "x": 45.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 116.0,
          "due_date": 146.0,
          "service_time": 10.0
        },
        {
          "id": 32,
          "x": 35.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 131.0,
          "due_date": 161.0,
          "service_time": 10.0
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
          "id": 51,
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
          "to": 48,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 13.0,
          "to_y": 52.0,
          "real_cost": 27.8,
          "reduced_cost": 475.477058
        },
        {
          "from": 48,
          "to": 47,
          "from_x": 13.0,
          "from_y": 52.0,
          "to_x": 8.0,
          "to_y": 56.0,
          "real_cost": 6.4,
          "reduced_cost": -5199.270562
        },
        {
          "from": 47,
          "to": 19,
          "from_x": 8.0,
          "from_y": 56.0,
          "to_x": 15.0,
          "to_y": 60.0,
          "real_cost": 8.0,
          "reduced_cost": 99.787759
        },
        {
          "from": 19,
          "to": 11,
          "from_x": 15.0,
          "from_y": 60.0,
          "to_x": 20.0,
          "to_y": 65.0,
          "real_cost": 7.0,
          "reduced_cost": 4078.122196
        },
        {
          "from": 11,
          "to": 10,
          "from_x": 20.0,
          "from_y": 65.0,
          "to_x": 30.0,
          "to_y": 60.0,
          "real_cost": 11.1,
          "reduced_cost": -9934.425488
        },
        {
          "from": 10,
          "to": 20,
          "from_x": 30.0,
          "from_y": 60.0,
          "to_x": 45.0,
          "to_y": 65.0,
          "real_cost": 15.8,
          "reduced_cost": -9943.185938
        },
        {
          "from": 20,
          "to": 32,
          "from_x": 45.0,
          "from_y": 65.0,
          "to_x": 35.0,
          "to_y": 69.0,
          "real_cost": 10.7,
          "reduced_cost": 10018.03771
        },
        {
          "from": 32,
          "to": 1,
          "from_x": 35.0,
          "from_y": 69.0,
          "to_x": 41.0,
          "to_y": 49.0,
          "real_cost": 20.8,
          "reduced_cost": 4219.852949
        },
        {
          "from": 1,
          "to": 51,
          "from_x": 41.0,
          "from_y": 49.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 15.2,
          "reduced_cost": 15.2
        }
      ],
      "color": "#65a30d"
    },
    {
      "id": 7,
      "name": "veic=7 col=0",
      "vehicle": 7,
      "sequence": [
        0,
        45,
        36,
        49,
        46,
        17,
        5,
        51
      ],
      "total_real_cost": 129.4,
      "total_reduced_cost": -0.0,
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
          "id": 45,
          "x": 6.0,
          "y": 38.0,
          "kind": "customer",
          "ready_time": 29.0,
          "due_date": 59.0,
          "service_time": 10.0
        },
        {
          "id": 36,
          "x": 2.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 41.0,
          "due_date": 71.0,
          "service_time": 10.0
        },
        {
          "id": 49,
          "x": 6.0,
          "y": 68.0,
          "kind": "customer",
          "ready_time": 98.0,
          "due_date": 128.0,
          "service_time": 10.0
        },
        {
          "id": 46,
          "x": 2.0,
          "y": 48.0,
          "kind": "customer",
          "ready_time": 107.0,
          "due_date": 137.0,
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
          "id": 51,
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
          "to": 45,
          "from_x": 35.0,
          "from_y": 35.0,
          "to_x": 6.0,
          "to_y": 38.0,
          "real_cost": 29.1,
          "reduced_cost": -9908.537136
        },
        {
          "from": 45,
          "to": 36,
          "from_x": 6.0,
          "from_y": 38.0,
          "to_x": 2.0,
          "to_y": 60.0,
          "real_cost": 22.3,
          "reduced_cost": -9913.830921
        },
        {
          "from": 36,
          "to": 49,
          "from_x": 2.0,
          "from_y": 60.0,
          "to_x": 6.0,
          "to_y": 68.0,
          "real_cost": 8.9,
          "reduced_cost": 262.644146
        },
        {
          "from": 49,
          "to": 46,
          "from_x": 6.0,
          "from_y": 68.0,
          "to_x": 2.0,
          "to_y": 48.0,
          "real_cost": 20.3,
          "reduced_cost": 838.394351
        },
        {
          "from": 46,
          "to": 17,
          "from_x": 2.0,
          "from_y": 48.0,
          "to_x": 5.0,
          "to_y": 30.0,
          "real_cost": 18.2,
          "reduced_cost": 7291.047514
        },
        {
          "from": 17,
          "to": 5,
          "from_x": 5.0,
          "from_y": 30.0,
          "to_x": 15.0,
          "to_y": 30.0,
          "real_cost": 10.0,
          "reduced_cost": 5239.27773
        },
        {
          "from": 5,
          "to": 51,
          "from_x": 15.0,
          "from_y": 30.0,
          "to_x": 35.0,
          "to_y": 35.0,
          "real_cost": 20.6,
          "reduced_cost": 20.6
        }
      ],
      "color": "#db2777"
    }
  ]
};
