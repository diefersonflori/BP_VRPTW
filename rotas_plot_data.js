window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 2",
  "subtitle": "Melhor inteira do pool | rotas ativas: 6",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=109",
      "vehicle": 0,
      "sequence": [
        0,
        45,
        46,
        8,
        7,
        6,
        4,
        5,
        3,
        1,
        51
      ],
      "total_real_cost": 104.8,
      "total_reduced_cost": 9.888127,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 45,
          "x": 20.0,
          "y": 82.0,
          "kind": "customer",
          "ready_time": 37.0,
          "due_date": 67.0,
          "service_time": 10.0
        },
        {
          "id": 46,
          "x": 18.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 192.0,
          "service_time": 10.0
        },
        {
          "id": 8,
          "x": 15.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 91.0,
          "due_date": 121.0,
          "service_time": 10.0
        },
        {
          "id": 7,
          "x": 15.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 6,
          "x": 18.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 95.0,
          "due_date": 125.0,
          "service_time": 10.0
        },
        {
          "id": 4,
          "x": 20.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 141.0,
          "due_date": 171.0,
          "service_time": 10.0
        },
        {
          "id": 5,
          "x": 20.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 189.0,
          "service_time": 10.0
        },
        {
          "id": 3,
          "x": 22.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 190.0,
          "service_time": 10.0
        },
        {
          "id": 1,
          "x": 25.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 191.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 45,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 20.0,
          "to_y": 82.0,
          "real_cost": 37.7,
          "reduced_cost": 37.040237
        },
        {
          "from": 45,
          "to": 46,
          "from_x": 20.0,
          "from_y": 82.0,
          "to_x": 18.0,
          "to_y": 80.0,
          "real_cost": 2.8,
          "reduced_cost": -29.508839
        },
        {
          "from": 46,
          "to": 8,
          "from_x": 18.0,
          "from_y": 80.0,
          "to_x": 15.0,
          "to_y": 80.0,
          "real_cost": 3.0,
          "reduced_cost": -21.811873
        },
        {
          "from": 8,
          "to": 7,
          "from_x": 15.0,
          "from_y": 80.0,
          "to_x": 15.0,
          "to_y": 75.0,
          "real_cost": 5.0,
          "reduced_cost": 4.0
        },
        {
          "from": 7,
          "to": 6,
          "from_x": 15.0,
          "from_y": 75.0,
          "to_x": 18.0,
          "to_y": 75.0,
          "real_cost": 3.0,
          "reduced_cost": 0.7
        },
        {
          "from": 6,
          "to": 4,
          "from_x": 18.0,
          "from_y": 75.0,
          "to_x": 20.0,
          "to_y": 80.0,
          "real_cost": 5.3,
          "reduced_cost": 3.871636
        },
        {
          "from": 4,
          "to": 5,
          "from_x": 20.0,
          "from_y": 80.0,
          "to_x": 20.0,
          "to_y": 85.0,
          "real_cost": 5.0,
          "reduced_cost": -21.71372
        },
        {
          "from": 5,
          "to": 3,
          "from_x": 20.0,
          "from_y": 85.0,
          "to_x": 22.0,
          "to_y": 85.0,
          "real_cost": 2.0,
          "reduced_cost": -6.911873
        },
        {
          "from": 3,
          "to": 1,
          "from_x": 22.0,
          "from_y": 85.0,
          "to_x": 25.0,
          "to_y": 85.0,
          "real_cost": 3.0,
          "reduced_cost": 5.285356
        },
        {
          "from": 1,
          "to": 51,
          "from_x": 25.0,
          "from_y": 85.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 38.0,
          "reduced_cost": 38.0
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=126",
      "vehicle": 1,
      "sequence": [
        0,
        12,
        14,
        11,
        9,
        10,
        13,
        16,
        17,
        47,
        51
      ],
      "total_real_cost": 110.7,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 12,
          "x": 8.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 197.0,
          "service_time": 10.0
        },
        {
          "id": 14,
          "x": 5.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 11,
          "x": 8.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 59.0,
          "due_date": 89.0,
          "service_time": 10.0
        },
        {
          "id": 9,
          "x": 10.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 91.0,
          "due_date": 121.0,
          "service_time": 10.0
        },
        {
          "id": 10,
          "x": 10.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 119.0,
          "due_date": 149.0,
          "service_time": 10.0
        },
        {
          "id": 13,
          "x": 5.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 142.0,
          "due_date": 172.0,
          "service_time": 10.0
        },
        {
          "id": 16,
          "x": 0.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 188.0,
          "service_time": 10.0
        },
        {
          "id": 17,
          "x": 0.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 149.0,
          "due_date": 179.0,
          "service_time": 10.0
        },
        {
          "id": 47,
          "x": 2.0,
          "y": 45.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 191.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 12,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 8.0,
          "to_y": 45.0,
          "real_cost": 32.3,
          "reduced_cost": 19.891821
        },
        {
          "from": 12,
          "to": 14,
          "from_x": 8.0,
          "from_y": 45.0,
          "to_x": 5.0,
          "to_y": 45.0,
          "real_cost": 3.0,
          "reduced_cost": -0.337203
        },
        {
          "from": 14,
          "to": 11,
          "from_x": 5.0,
          "from_y": 45.0,
          "to_x": 8.0,
          "to_y": 40.0,
          "real_cost": 5.8,
          "reduced_cost": 18.243404
        },
        {
          "from": 11,
          "to": 9,
          "from_x": 8.0,
          "from_y": 40.0,
          "to_x": 10.0,
          "to_y": 35.0,
          "real_cost": 5.3,
          "reduced_cost": -5.637203
        },
        {
          "from": 9,
          "to": 10,
          "from_x": 10.0,
          "from_y": 35.0,
          "to_x": 10.0,
          "to_y": 40.0,
          "real_cost": 5.0,
          "reduced_cost": -18.043404
        },
        {
          "from": 10,
          "to": 13,
          "from_x": 10.0,
          "from_y": 40.0,
          "to_x": 5.0,
          "to_y": 35.0,
          "real_cost": 7.0,
          "reduced_cost": -27.365831
        },
        {
          "from": 13,
          "to": 16,
          "from_x": 5.0,
          "from_y": 35.0,
          "to_x": 0.0,
          "to_y": 40.0,
          "real_cost": 7.0,
          "reduced_cost": 2.462797
        },
        {
          "from": 16,
          "to": 17,
          "from_x": 0.0,
          "from_y": 40.0,
          "to_x": 0.0,
          "to_y": 45.0,
          "real_cost": 5.0,
          "reduced_cost": -0.337203
        },
        {
          "from": 17,
          "to": 47,
          "from_x": 0.0,
          "from_y": 45.0,
          "to_x": 2.0,
          "to_y": 45.0,
          "real_cost": 2.0,
          "reduced_cost": -27.177177
        },
        {
          "from": 47,
          "to": 51,
          "from_x": 2.0,
          "from_y": 45.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 38.3,
          "reduced_cost": 38.3
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
        37,
        42,
        36,
        39,
        44,
        40,
        38,
        41,
        35,
        43,
        51
      ],
      "total_real_cost": 155.0,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 37,
          "x": 65.0,
          "y": 82.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 189.0,
          "service_time": 10.0
        },
        {
          "id": 42,
          "x": 55.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 33.0,
          "due_date": 63.0,
          "service_time": 10.0
        },
        {
          "id": 36,
          "x": 65.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 43.0,
          "due_date": 73.0,
          "service_time": 10.0
        },
        {
          "id": 39,
          "x": 60.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 37.0,
          "due_date": 67.0,
          "service_time": 10.0
        },
        {
          "id": 44,
          "x": 55.0,
          "y": 82.0,
          "kind": "customer",
          "ready_time": 64.0,
          "due_date": 94.0,
          "service_time": 10.0
        },
        {
          "id": 40,
          "x": 60.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 85.0,
          "due_date": 115.0,
          "service_time": 10.0
        },
        {
          "id": 38,
          "x": 62.0,
          "y": 80.0,
          "kind": "customer",
          "ready_time": 75.0,
          "due_date": 105.0,
          "service_time": 10.0
        },
        {
          "id": 41,
          "x": 58.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 92.0,
          "due_date": 122.0,
          "service_time": 10.0
        },
        {
          "id": 35,
          "x": 67.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 139.0,
          "due_date": 169.0,
          "service_time": 10.0
        },
        {
          "id": 43,
          "x": 55.0,
          "y": 85.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 191.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 37,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 65.0,
          "to_y": 82.0,
          "real_cost": 40.6,
          "reduced_cost": 52.045119
        },
        {
          "from": 37,
          "to": 42,
          "from_x": 65.0,
          "from_y": 82.0,
          "to_x": 55.0,
          "to_y": 80.0,
          "real_cost": 10.1,
          "reduced_cost": -5.362797
        },
        {
          "from": 42,
          "to": 36,
          "from_x": 55.0,
          "from_y": 80.0,
          "to_x": 65.0,
          "to_y": 85.0,
          "real_cost": 11.1,
          "reduced_cost": -10.158839
        },
        {
          "from": 36,
          "to": 39,
          "from_x": 65.0,
          "from_y": 85.0,
          "to_x": 60.0,
          "to_y": 80.0,
          "real_cost": 7.0,
          "reduced_cost": 1.762797
        },
        {
          "from": 39,
          "to": 44,
          "from_x": 60.0,
          "from_y": 80.0,
          "to_x": 55.0,
          "to_y": 82.0,
          "real_cost": 5.3,
          "reduced_cost": -32.818602
        },
        {
          "from": 44,
          "to": 40,
          "from_x": 55.0,
          "from_y": 82.0,
          "to_x": 60.0,
          "to_y": 85.0,
          "real_cost": 5.8,
          "reduced_cost": -15.362797
        },
        {
          "from": 40,
          "to": 38,
          "from_x": 60.0,
          "from_y": 85.0,
          "to_x": 62.0,
          "to_y": 80.0,
          "real_cost": 5.3,
          "reduced_cost": -14.9
        },
        {
          "from": 38,
          "to": 41,
          "from_x": 62.0,
          "from_y": 80.0,
          "to_x": 58.0,
          "to_y": 75.0,
          "real_cost": 6.4,
          "reduced_cost": -16.241161
        },
        {
          "from": 41,
          "to": 35,
          "from_x": 58.0,
          "from_y": 75.0,
          "to_x": 67.0,
          "to_y": 85.0,
          "real_cost": 13.4,
          "reduced_cost": -17.16372
        },
        {
          "from": 35,
          "to": 43,
          "from_x": 67.0,
          "from_y": 85.0,
          "to_x": 55.0,
          "to_y": 85.0,
          "real_cost": 12.0,
          "reduced_cost": 20.2
        },
        {
          "from": 43,
          "to": 51,
          "from_x": 55.0,
          "from_y": 85.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 38.0,
          "reduced_cost": 38.0
        }
      ],
      "color": "#0f766e"
    },
    {
      "id": 3,
      "name": "veic=3 col=160",
      "vehicle": 3,
      "sequence": [
        0,
        33,
        27,
        30,
        32,
        28,
        26,
        29,
        34,
        50,
        51
      ],
      "total_real_cost": 143.4,
      "total_reduced_cost": 0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 33,
          "x": 85.0,
          "y": 25.0,
          "kind": "customer",
          "ready_time": 51.0,
          "due_date": 81.0,
          "service_time": 10.0
        },
        {
          "id": 27,
          "x": 95.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 62.0,
          "due_date": 92.0,
          "service_time": 10.0
        },
        {
          "id": 30,
          "x": 88.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 74.0,
          "due_date": 104.0,
          "service_time": 10.0
        },
        {
          "id": 32,
          "x": 87.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 178.0,
          "service_time": 10.0
        },
        {
          "id": 28,
          "x": 92.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 174.0,
          "service_time": 10.0
        },
        {
          "id": 26,
          "x": 95.0,
          "y": 30.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 171.0,
          "service_time": 10.0
        },
        {
          "id": 29,
          "x": 90.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 177.0,
          "service_time": 10.0
        },
        {
          "id": 34,
          "x": 85.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 182.0,
          "service_time": 10.0
        },
        {
          "id": 50,
          "x": 72.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 33,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 85.0,
          "to_y": 25.0,
          "real_cost": 51.4,
          "reduced_cost": 27.477778
        },
        {
          "from": 33,
          "to": 27,
          "from_x": 85.0,
          "from_y": 25.0,
          "to_x": 95.0,
          "to_y": 35.0,
          "real_cost": 14.1,
          "reduced_cost": -14.522222
        },
        {
          "from": 27,
          "to": 30,
          "from_x": 95.0,
          "from_y": 35.0,
          "to_x": 88.0,
          "to_y": 30.0,
          "real_cost": 8.6,
          "reduced_cost": -12.322222
        },
        {
          "from": 30,
          "to": 32,
          "from_x": 88.0,
          "from_y": 30.0,
          "to_x": 87.0,
          "to_y": 30.0,
          "real_cost": 1.0,
          "reduced_cost": -11.222222
        },
        {
          "from": 32,
          "to": 28,
          "from_x": 87.0,
          "from_y": 30.0,
          "to_x": 92.0,
          "to_y": 30.0,
          "real_cost": 5.0,
          "reduced_cost": -5.222222
        },
        {
          "from": 28,
          "to": 26,
          "from_x": 92.0,
          "from_y": 30.0,
          "to_x": 95.0,
          "to_y": 30.0,
          "real_cost": 3.0,
          "reduced_cost": -11.922222
        },
        {
          "from": 26,
          "to": 29,
          "from_x": 95.0,
          "from_y": 30.0,
          "to_x": 90.0,
          "to_y": 35.0,
          "real_cost": 7.0,
          "reduced_cost": -3.622222
        },
        {
          "from": 29,
          "to": 34,
          "from_x": 90.0,
          "from_y": 35.0,
          "to_x": 85.0,
          "to_y": 35.0,
          "real_cost": 5.0,
          "reduced_cost": -5.222222
        },
        {
          "from": 34,
          "to": 50,
          "from_x": 85.0,
          "from_y": 35.0,
          "to_x": 72.0,
          "to_y": 35.0,
          "real_cost": 13.0,
          "reduced_cost": 1.877778
        },
        {
          "from": 50,
          "to": 51,
          "from_x": 72.0,
          "from_y": 35.0,
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
      "name": "veic=4 col=1",
      "vehicle": 4,
      "sequence": [
        0,
        20,
        18,
        48,
        21,
        23,
        22,
        49,
        19,
        25,
        24,
        51
      ],
      "total_real_cost": 120.8,
      "total_reduced_cost": -0.0,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 20,
          "x": 42.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 18,
          "x": 44.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 184.0,
          "service_time": 10.0
        },
        {
          "id": 48,
          "x": 42.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 184.0,
          "service_time": 10.0
        },
        {
          "id": 21,
          "x": 40.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 185.0,
          "service_time": 10.0
        },
        {
          "id": 23,
          "x": 38.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 65.0,
          "due_date": 95.0,
          "service_time": 10.0
        },
        {
          "id": 22,
          "x": 40.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 92.0,
          "due_date": 122.0,
          "service_time": 10.0
        },
        {
          "id": 49,
          "x": 42.0,
          "y": 12.0,
          "kind": "customer",
          "ready_time": 104.0,
          "due_date": 134.0,
          "service_time": 10.0
        },
        {
          "id": 19,
          "x": 42.0,
          "y": 10.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 189.0,
          "service_time": 10.0
        },
        {
          "id": 25,
          "x": 35.0,
          "y": 5.0,
          "kind": "customer",
          "ready_time": 154.0,
          "due_date": 184.0,
          "service_time": 10.0
        },
        {
          "id": 24,
          "x": 38.0,
          "y": 15.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 194.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 20,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 42.0,
          "to_y": 15.0,
          "real_cost": 35.0,
          "reduced_cost": 29.853562
        },
        {
          "from": 20,
          "to": 18,
          "from_x": 42.0,
          "from_y": 15.0,
          "to_x": 44.0,
          "to_y": 5.0,
          "real_cost": 10.1,
          "reduced_cost": 0.914248
        },
        {
          "from": 18,
          "to": 48,
          "from_x": 44.0,
          "from_y": 5.0,
          "to_x": 42.0,
          "to_y": 5.0,
          "real_cost": 2.0,
          "reduced_cost": -3.43219
        },
        {
          "from": 48,
          "to": 21,
          "from_x": 42.0,
          "from_y": 5.0,
          "to_x": 40.0,
          "to_y": 5.0,
          "real_cost": 2.0,
          "reduced_cost": 7.49657
        },
        {
          "from": 21,
          "to": 23,
          "from_x": 40.0,
          "from_y": 5.0,
          "to_x": 38.0,
          "to_y": 5.0,
          "real_cost": 2.0,
          "reduced_cost": -20.165963
        },
        {
          "from": 23,
          "to": 22,
          "from_x": 38.0,
          "from_y": 5.0,
          "to_x": 40.0,
          "to_y": 15.0,
          "real_cost": 10.1,
          "reduced_cost": -20.365435
        },
        {
          "from": 22,
          "to": 49,
          "from_x": 40.0,
          "from_y": 15.0,
          "to_x": 42.0,
          "to_y": 12.0,
          "real_cost": 3.6,
          "reduced_cost": 3.6
        },
        {
          "from": 49,
          "to": 19,
          "from_x": 42.0,
          "from_y": 12.0,
          "to_x": 42.0,
          "to_y": 10.0,
          "real_cost": 2.0,
          "reduced_cost": -40.470185
        },
        {
          "from": 19,
          "to": 25,
          "from_x": 42.0,
          "from_y": 10.0,
          "to_x": 35.0,
          "to_y": 5.0,
          "real_cost": 8.6,
          "reduced_cost": -9.078628
        },
        {
          "from": 25,
          "to": 24,
          "from_x": 35.0,
          "from_y": 5.0,
          "to_x": 38.0,
          "to_y": 15.0,
          "real_cost": 10.4,
          "reduced_cost": 16.648021
        },
        {
          "from": 24,
          "to": 51,
          "from_x": 38.0,
          "from_y": 15.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 35.0,
          "reduced_cost": 35.0
        }
      ],
      "color": "#ea580c"
    },
    {
      "id": 5,
      "name": "veic=5 col=9",
      "vehicle": 5,
      "sequence": [
        0,
        2,
        15,
        31,
        51
      ],
      "total_real_cost": 207.4,
      "total_reduced_cost": 179.289651,
      "nodes": [
        {
          "id": 0,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_start",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        },
        {
          "id": 2,
          "x": 22.0,
          "y": 75.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 199.0,
          "service_time": 10.0
        },
        {
          "id": 15,
          "x": 2.0,
          "y": 40.0,
          "kind": "customer",
          "ready_time": 58.0,
          "due_date": 88.0,
          "service_time": 10.0
        },
        {
          "id": 31,
          "x": 88.0,
          "y": 35.0,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 179.0,
          "service_time": 10.0
        },
        {
          "id": 51,
          "x": 40.0,
          "y": 50.0,
          "kind": "depot_end",
          "ready_time": 0.0,
          "due_date": 240.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 2,
          "from_x": 40.0,
          "from_y": 50.0,
          "to_x": 22.0,
          "to_y": 75.0,
          "real_cost": 30.8,
          "reduced_cost": 21.549077
        },
        {
          "from": 2,
          "to": 15,
          "from_x": 22.0,
          "from_y": 75.0,
          "to_x": 2.0,
          "to_y": 40.0,
          "real_cost": 40.3,
          "reduced_cost": 31.662797
        },
        {
          "from": 15,
          "to": 31,
          "from_x": 2.0,
          "from_y": 40.0,
          "to_x": 88.0,
          "to_y": 35.0,
          "real_cost": 86.1,
          "reduced_cost": 75.877778
        },
        {
          "from": 31,
          "to": 51,
          "from_x": 88.0,
          "from_y": 35.0,
          "to_x": 40.0,
          "to_y": 50.0,
          "real_cost": 50.2,
          "reduced_cost": 50.2
        }
      ],
      "color": "#0891b2"
    }
  ]
};
