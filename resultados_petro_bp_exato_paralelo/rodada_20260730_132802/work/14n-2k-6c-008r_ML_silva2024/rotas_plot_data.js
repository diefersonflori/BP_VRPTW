window.ROUTE_PLOT_DATA = {
  "title": "Solução inteira do nó 64",
  "subtitle": "Melhor inteira do pool | rotas ativas: 2",
  "routes": [
    {
      "id": 0,
      "name": "veic=0 col=71",
      "vehicle": 0,
      "sequence": [
        0,
        5,
        8,
        9,
        10,
        7,
        6,
        1,
        2,
        4,
        3,
        15
      ],
      "total_real_cost": 135728.0,
      "total_reduced_cost": 135642.058706,
      "nodes": [
        {
          "id": 0,
          "x": -41.77,
          "y": -21.83,
          "kind": "depot_start",
          "ready_time": 25200.0,
          "due_date": 345600.0,
          "service_time": 0.0
        },
        {
          "id": 5,
          "x": -40.089,
          "y": -22.359,
          "kind": "customer",
          "ready_time": 14400.0,
          "due_date": 403200.0,
          "service_time": 2278.0
        },
        {
          "id": 8,
          "x": -40.196,
          "y": -22.344,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 277200.0,
          "service_time": 2158.0
        },
        {
          "id": 9,
          "x": -40.196,
          "y": -22.344,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 277200.0,
          "service_time": 3956.0
        },
        {
          "id": 10,
          "x": -40.196,
          "y": -22.344,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 277200.0,
          "service_time": 9494.0
        },
        {
          "id": 7,
          "x": -39.948,
          "y": -22.447,
          "kind": "customer",
          "ready_time": 79200.0,
          "due_date": 532800.0,
          "service_time": 13041.0
        },
        {
          "id": 6,
          "x": -39.948,
          "y": -22.447,
          "kind": "customer",
          "ready_time": 79200.0,
          "due_date": 532800.0,
          "service_time": 12945.0
        },
        {
          "id": 1,
          "x": -40.242,
          "y": -22.351,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 518400.0,
          "service_time": 1918.0
        },
        {
          "id": 2,
          "x": -40.067,
          "y": -22.547,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 435600.0,
          "service_time": 3237.0
        },
        {
          "id": 4,
          "x": -40.067,
          "y": -22.547,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 435600.0,
          "service_time": 18023.0
        },
        {
          "id": 3,
          "x": -40.067,
          "y": -22.547,
          "kind": "customer",
          "ready_time": 0.0,
          "due_date": 435600.0,
          "service_time": 1678.0
        },
        {
          "id": 15,
          "x": -41.77,
          "y": -21.83,
          "kind": "depot_end",
          "ready_time": 25200.0,
          "due_date": 345600.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 5,
          "from_x": -41.77,
          "from_y": -21.83,
          "to_x": -40.089,
          "to_y": -22.359,
          "real_cost": 51848.0,
          "reduced_cost": 3051590.646814
        },
        {
          "from": 5,
          "to": 8,
          "from_x": -40.089,
          "from_y": -22.359,
          "to_x": -40.196,
          "to_y": -22.344,
          "real_cost": 4262.0,
          "reduced_cost": -995713.269572
        },
        {
          "from": 8,
          "to": 9,
          "from_x": -40.196,
          "from_y": -22.344,
          "to_x": -40.196,
          "to_y": -22.344,
          "real_cost": 0.0,
          "reduced_cost": -999978.560297
        },
        {
          "from": 9,
          "to": 10,
          "from_x": -40.196,
          "from_y": -22.344,
          "to_x": -40.196,
          "to_y": -22.344,
          "real_cost": 0.0,
          "reduced_cost": 24.170062
        },
        {
          "from": 10,
          "to": 7,
          "from_x": -40.196,
          "from_y": -22.344,
          "to_x": -39.948,
          "to_y": -22.447,
          "real_cost": 7923.0,
          "reduced_cost": 7917.401143
        },
        {
          "from": 7,
          "to": 6,
          "from_x": -39.948,
          "from_y": -22.447,
          "to_x": -39.948,
          "to_y": -22.447,
          "real_cost": 0.0,
          "reduced_cost": -7.44378
        },
        {
          "from": 6,
          "to": 1,
          "from_x": -39.948,
          "from_y": -22.447,
          "to_x": -40.242,
          "to_y": -22.351,
          "real_cost": 9086.0,
          "reduced_cost": 9115.66471
        },
        {
          "from": 1,
          "to": 2,
          "from_x": -40.242,
          "from_y": -22.351,
          "to_x": -40.067,
          "to_y": -22.547,
          "real_cost": 8010.0,
          "reduced_cost": -991959.550374
        },
        {
          "from": 2,
          "to": 4,
          "from_x": -40.067,
          "from_y": -22.547,
          "to_x": -40.067,
          "to_y": -22.547,
          "real_cost": 0.0,
          "reduced_cost": 27.0
        },
        {
          "from": 4,
          "to": 3,
          "from_x": -40.067,
          "from_y": -22.547,
          "to_x": -40.067,
          "to_y": -22.547,
          "real_cost": 0.0,
          "reduced_cost": 27.0
        },
        {
          "from": 3,
          "to": 15,
          "from_x": -40.067,
          "from_y": -22.547,
          "to_x": -41.77,
          "to_y": -21.83,
          "real_cost": 54599.0,
          "reduced_cost": 54599.0
        }
      ],
      "color": "#2563eb"
    },
    {
      "id": 1,
      "name": "veic=1 col=32",
      "vehicle": 1,
      "sequence": [
        0,
        11,
        12,
        13,
        14,
        15
      ],
      "total_real_cost": 109242.0,
      "total_reduced_cost": 109160.685954,
      "nodes": [
        {
          "id": 0,
          "x": -41.77,
          "y": -21.83,
          "kind": "depot_start",
          "ready_time": 25200.0,
          "due_date": 345600.0,
          "service_time": 0.0
        },
        {
          "id": 11,
          "x": -40.03,
          "y": -22.467,
          "kind": "customer",
          "ready_time": 255600.0,
          "due_date": 752400.0,
          "service_time": 1798.0
        },
        {
          "id": 12,
          "x": -40.03,
          "y": -22.467,
          "kind": "customer",
          "ready_time": 255600.0,
          "due_date": 752400.0,
          "service_time": 2038.0
        },
        {
          "id": 13,
          "x": -40.03,
          "y": -22.467,
          "kind": "customer",
          "ready_time": 255600.0,
          "due_date": 752400.0,
          "service_time": 11801.0
        },
        {
          "id": 14,
          "x": -40.03,
          "y": -22.467,
          "kind": "customer",
          "ready_time": 255600.0,
          "due_date": 752400.0,
          "service_time": 24552.0
        },
        {
          "id": 15,
          "x": -41.77,
          "y": -21.83,
          "kind": "depot_end",
          "ready_time": 25200.0,
          "due_date": 345600.0,
          "service_time": 0.0
        }
      ],
      "arcs": [
        {
          "from": 0,
          "to": 11,
          "from_x": -41.77,
          "from_y": -21.83,
          "to_x": -40.03,
          "to_y": -22.467,
          "real_cost": 54621.0,
          "reduced_cost": 54614.651226
        },
        {
          "from": 11,
          "to": 12,
          "from_x": -40.03,
          "from_y": -22.467,
          "to_x": -40.03,
          "to_y": -22.467,
          "real_cost": 0.0,
          "reduced_cost": -22.483945
        },
        {
          "from": 12,
          "to": 13,
          "from_x": -40.03,
          "from_y": -22.467,
          "to_x": -40.03,
          "to_y": -22.467,
          "real_cost": 0.0,
          "reduced_cost": -25.481327
        },
        {
          "from": 13,
          "to": 14,
          "from_x": -40.03,
          "from_y": -22.467,
          "to_x": -40.03,
          "to_y": -22.467,
          "real_cost": 0.0,
          "reduced_cost": -27.0
        },
        {
          "from": 14,
          "to": 15,
          "from_x": -40.03,
          "from_y": -22.467,
          "to_x": -41.77,
          "to_y": -21.83,
          "real_cost": 54621.0,
          "reduced_cost": 54621.0
        }
      ],
      "color": "#ef4444"
    }
  ]
};
