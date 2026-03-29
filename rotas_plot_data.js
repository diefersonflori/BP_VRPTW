window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 14",
  "subtitle": "Melhor inteira do pool | rotas ativas: 3",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=73",
      "vehicle": 0,
      "sequence": [
        0,
        8,
        21,
        22,
        20,
        26
      ],
      "total_real_cost": 34.619321,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 3390.0,
          "service_time": 0.0
        },
        {
          "id": 8,
          "x": 34.0,
          "y": 60.0,
          "kind": "customer",
          "ready_time": 2887.0,
          "due_date": 3047.0,
          "service_time": 90.0
        },
        {
          "id": 21,
          "x": 30.0,
          "y": 56.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3288.0,
          "service_time": 90.0
        },
        {
          "id": 22,
          "x": 28.0,
          "y": 52.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3287.0,
          "service_time": 90.0
        },
        {
          "id": 20,
          "x": 30.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3290.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 3390.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 8,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 34.0,
          "to_y": 60.0,
          "real_cost": 11.661904,
          "reduced_cost": 5.130288
        },
        {
          "from": 8,
          "to": 21,
          "from_x": 34.0,
          "from_y": 60.0,
          "to_x": 30.0,
          "to_y": 56.0,
          "real_cost": 5.656854,
          "reduced_cost": -2.178391
        },
        {
          "from": 21,
          "to": 22,
          "from_x": 30.0,
          "from_y": 56.0,
          "to_x": 28.0,
          "to_y": 52.0,
          "real_cost": 4.472136,
          "reduced_cost": -2.378431
        },
        {
          "from": 22,
          "to": 20,
          "from_x": 28.0,
          "from_y": 52.0,
          "to_x": 30.0,
          "to_y": 50.0,
          "real_cost": 2.828427,
          "reduced_cost": -10.573467
        },
        {
          "from": 20,
          "to": 26,
          "from_x": 30.0,
          "from_y": 50.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 10.0,
          "reduced_cost": 10.0
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=246",
      "vehicle": 1,
      "sequence": [
        0,
        24,
        6,
        23,
        17,
        18,
        19,
        15,
        13,
        25,
        26
      ],
      "total_real_cost": 112.441996,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 3390.0,
          "service_time": 0.0
        },
        {
          "id": 24,
          "x": 25.0,
          "y": 50.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3285.0,
          "service_time": 90.0
        },
        {
          "id": 6,
          "x": 16.0,
          "y": 42.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3274.0,
          "service_time": 90.0
        },
        {
          "id": 23,
          "x": 14.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 1643.0,
          "due_date": 1803.0,
          "service_time": 90.0
        },
        {
          "id": 17,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3266.0,
          "service_time": 90.0
        },
        {
          "id": 18,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3264.0,
          "service_time": 90.0
        },
        {
          "id": 19,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3260.0,
          "service_time": 90.0
        },
        {
          "id": 15,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 2216.0,
          "due_date": 2376.0,
          "service_time": 90.0
        },
        {
          "id": 13,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 2405.0,
          "due_date": 2565.0,
          "service_time": 90.0
        },
        {
          "id": 25,
          "x": 22.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 2504.0,
          "due_date": 2664.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 3390.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 24,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 25.0,
          "to_y": 50.0,
          "real_cost": 15.0,
          "reduced_cost": -6.432945
        },
        {
          "from": 24,
          "to": 6,
          "from_x": 25.0,
          "from_y": 50.0,
          "to_x": 16.0,
          "to_y": 42.0,
          "real_cost": 12.041595,
          "reduced_cost": -12.38926
        },
        {
          "from": 6,
          "to": 23,
          "from_x": 16.0,
          "from_y": 42.0,
          "to_x": 14.0,
          "to_y": 66.0,
          "real_cost": 24.083189,
          "reduced_cost": 14.28672
        },
        {
          "from": 23,
          "to": 17,
          "from_x": 14.0,
          "from_y": 66.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 9.848858,
          "reduced_cost": -2.36765
        },
        {
          "from": 17,
          "to": 18,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 3.0,
          "reduced_cost": 0.494642
        },
        {
          "from": 18,
          "to": 19,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": -1.275836
        },
        {
          "from": 19,
          "to": 15,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.0,
          "reduced_cost": -6.766601
        },
        {
          "from": 15,
          "to": 13,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 5.385165,
          "reduced_cost": -3.008409
        },
        {
          "from": 13,
          "to": 25,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 22.0,
          "to_y": 66.0,
          "real_cost": 9.0,
          "reduced_cost": -6.62385
        },
        {
          "from": 25,
          "to": 26,
          "from_x": 22.0,
          "from_y": 66.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 24.083189,
          "reduced_cost": 24.083189
        }
      ],
      "color": "#ef4444"
    },
    {
      "id": 2,
      "name": "veic=2 col=616",
      "vehicle": 2,
      "sequence": [
        0,
        5,
        2,
        4,
        3,
        7,
        1,
        12,
        14,
        16,
        9,
        11,
        10,
        26
      ],
      "total_real_cost": 129.653262,
      "total_reduced_cost": -0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 3390.0,
          "service_time": 0.0
        },
        {
          "id": 5,
          "x": 42.0,
          "y": 65.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3284.0,
          "service_time": 90.0
        },
        {
          "id": 2,
          "x": 45.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3279.0,
          "service_time": 90.0
        },
        {
          "id": 4,
          "x": 60.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 1261.0,
          "due_date": 1421.0,
          "service_time": 90.0
        },
        {
          "id": 3,
          "x": 62.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3270.0,
          "service_time": 90.0
        },
        {
          "id": 7,
          "x": 58.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3273.0,
          "service_time": 90.0
        },
        {
          "id": 1,
          "x": 52.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3272.0,
          "service_time": 90.0
        },
        {
          "id": 12,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3261.0,
          "service_time": 90.0
        },
        {
          "id": 14,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3260.0,
          "service_time": 90.0
        },
        {
          "id": 16,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3259.0,
          "service_time": 90.0
        },
        {
          "id": 9,
          "x": 28.0,
          "y": 70.0,
          "kind": "customer",
          "ready_time": 2601.0,
          "due_date": 2761.0,
          "service_time": 90.0
        },
        {
          "id": 11,
          "x": 35.0,
          "y": 69.0,
          "kind": "customer",
          "ready_time": 2698.0,
          "due_date": 2858.0,
          "service_time": 90.0
        },
        {
          "id": 10,
          "x": 35.0,
          "y": 66.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 3283.0,
          "service_time": 90.0
        },
        {
          "id": 26,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 3390.0,
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
          "real_cost": 15.132746,
          "reduced_cost": 1000010.826177
        },
        {
          "from": 5,
          "to": 2,
          "from_x": 42.0,
          "from_y": 65.0,
          "to_x": 45.0,
          "to_y": 70.0,
          "real_cost": 5.830952,
          "reduced_cost": -1000011.655483
        },
        {
          "from": 2,
          "to": 4,
          "from_x": 45.0,
          "from_y": 70.0,
          "to_x": 60.0,
          "to_y": 66.0,
          "real_cost": 15.524175,
          "reduced_cost": -999986.977601
        },
        {
          "from": 4,
          "to": 3,
          "from_x": 60.0,
          "from_y": 66.0,
          "to_x": 62.0,
          "to_y": 69.0,
          "real_cost": 3.605551,
          "reduced_cost": -23.472298
        },
        {
          "from": 3,
          "to": 7,
          "from_x": 62.0,
          "from_y": 69.0,
          "to_x": 58.0,
          "to_y": 70.0,
          "real_cost": 4.123106,
          "reduced_cost": 1.676775
        },
        {
          "from": 7,
          "to": 1,
          "from_x": 58.0,
          "from_y": 70.0,
          "to_x": 52.0,
          "to_y": 75.0,
          "real_cost": 7.81025,
          "reduced_cost": 2.222796
        },
        {
          "from": 1,
          "to": 12,
          "from_x": 52.0,
          "from_y": 75.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 28.79236,
          "reduced_cost": 20.088164
        },
        {
          "from": 12,
          "to": 14,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": 1.021852
        },
        {
          "from": 14,
          "to": 16,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 2.0,
          "reduced_cost": -16.650543
        },
        {
          "from": 16,
          "to": 9,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 28.0,
          "to_y": 70.0,
          "real_cost": 17.0,
          "reduced_cost": 10.507839
        },
        {
          "from": 9,
          "to": 11,
          "from_x": 28.0,
          "from_y": 70.0,
          "to_x": 35.0,
          "to_y": 69.0,
          "real_cost": 7.071068,
          "reduced_cost": 999977.204137
        },
        {
          "from": 11,
          "to": 10,
          "from_x": 35.0,
          "from_y": 69.0,
          "to_x": 35.0,
          "to_y": 66.0,
          "real_cost": 3.0,
          "reduced_cost": -1.554868
        },
        {
          "from": 10,
          "to": 26,
          "from_x": 35.0,
          "from_y": 66.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 16.763055,
          "reduced_cost": 16.763055
        }
      ],
      "color": "#0f766e"
    }
  ]
};
