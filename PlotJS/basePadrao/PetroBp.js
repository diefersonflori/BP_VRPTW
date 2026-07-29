window.DADOS = {
  "instancia": "EXEMPLO_PETRO_CARGA_A_BORDO_4_NAVIOS",
  "horizonte_h": 168.0,
  "fo_total_s": 231840.0,
  "nos": [
    {
      "id": 0,
      "nome": "BASE_PACU",
      "plataforma": "BASE",
      "lat": -21.845602,
      "lon": -40.996652,
      "janelas": [
        [
          0.0,
          168.0
        ]
      ],
      "servico_h": 0.0,
      "deck": 0.0,
      "deck_load": 0.0,
      "deck_backload": 0.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 1,
      "nome": "P-09_order_1",
      "plataforma": "P-09",
      "lat": -22.364,
      "lon": -40.214,
      "janelas": [
        [
          8.0,
          24.0
        ],
        [
          32.0,
          48.0
        ]
      ],
      "servico_h": 1.0,
      "deck": 20.0,
      "deck_load": 0.0,
      "deck_backload": 20.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 2,
      "nome": "P-09_order_2",
      "plataforma": "P-09",
      "lat": -22.364,
      "lon": -40.214,
      "janelas": [
        [
          8.0,
          24.0
        ],
        [
          32.0,
          48.0
        ]
      ],
      "servico_h": 2.0,
      "deck": 120.0,
      "deck_load": 120.0,
      "deck_backload": 0.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 3,
      "nome": "P-43_order_3",
      "plataforma": "P-43",
      "lat": -22.733,
      "lon": -40.161,
      "janelas": [
        [
          16.0,
          40.0
        ]
      ],
      "servico_h": 3.0,
      "deck": 80.0,
      "deck_load": 80.0,
      "deck_backload": 0.0,
      "diesel": 100.0,
      "agua": 150.0
    },
    {
      "id": 4,
      "nome": "P-51_order_4",
      "plataforma": "P-51",
      "lat": -23.125,
      "lon": -40.302,
      "janelas": [
        [
          10.0,
          28.0
        ],
        [
          52.0,
          74.0
        ]
      ],
      "servico_h": 1.0,
      "deck": 35.0,
      "deck_load": 0.0,
      "deck_backload": 35.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 5,
      "nome": "P-51_order_5",
      "plataforma": "P-51",
      "lat": -23.125,
      "lon": -40.302,
      "janelas": [
        [
          10.0,
          28.0
        ],
        [
          52.0,
          74.0
        ]
      ],
      "servico_h": 1.5,
      "deck": 140.0,
      "deck_load": 140.0,
      "deck_backload": 0.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 6,
      "nome": "P-40_order_6",
      "plataforma": "P-40",
      "lat": -22.798,
      "lon": -40.439,
      "janelas": [
        [
          20.0,
          46.0
        ]
      ],
      "servico_h": 2.5,
      "deck": 60.0,
      "deck_load": 60.0,
      "deck_backload": 0.0,
      "diesel": 80.0,
      "agua": 0.0
    },
    {
      "id": 7,
      "nome": "P-40_order_7",
      "plataforma": "P-40",
      "lat": -22.798,
      "lon": -40.439,
      "janelas": [
        [
          20.0,
          46.0
        ]
      ],
      "servico_h": 2.0,
      "deck": 0.0,
      "deck_load": 0.0,
      "deck_backload": 0.0,
      "diesel": 0.0,
      "agua": 180.0
    },
    {
      "id": 8,
      "nome": "P-38_order_8",
      "plataforma": "P-38",
      "lat": -22.561,
      "lon": -40.123,
      "janelas": [
        [
          12.0,
          34.0
        ]
      ],
      "servico_h": 1.0,
      "deck": 25.0,
      "deck_load": 0.0,
      "deck_backload": 25.0,
      "diesel": 0.0,
      "agua": 0.0
    },
    {
      "id": 9,
      "nome": "P-38_order_9",
      "plataforma": "P-38",
      "lat": -22.561,
      "lon": -40.123,
      "janelas": [
        [
          12.0,
          34.0
        ]
      ],
      "servico_h": 2.0,
      "deck": 110.0,
      "deck_load": 110.0,
      "deck_backload": 0.0,
      "diesel": 0.0,
      "agua": 90.0
    },
    {
      "id": 10,
      "nome": "P-55_order_10",
      "plataforma": "P-55",
      "lat": -22.973,
      "lon": -40.048,
      "janelas": [
        [
          30.0,
          60.0
        ]
      ],
      "servico_h": 2.5,
      "deck": 70.0,
      "deck_load": 70.0,
      "deck_backload": 0.0,
      "diesel": 120.0,
      "agua": 0.0
    }
  ],
  "navios": [
    {
      "k": 0,
      "nome": "STARNAV TAURUS",
      "ocioso": false,
      "capacidades": {
        "deck": 300.0,
        "diesel": 200.0,
        "agua": 300.0
      },
      "carga_inicial": {
        "deck": 200.0,
        "diesel": 100.0,
        "agua": 150.0
      },
      "pico_deck": 220.0,
      "cargas": [
        {
          "tipo": "base",
          "nome": "Saida da base",
          "deck_depois": 200.0,
          "diesel_depois": 100.0,
          "agua_depois": 150.0
        },
        {
          "tipo": "visita",
          "no": 1,
          "nome": "P-09_order_1",
          "plataforma": "P-09",
          "deck_antes": 200,
          "deck_coleta": 20,
          "deck_pico": 220,
          "deck_entrega": 0,
          "deck_depois": 220,
          "diesel_antes": 100,
          "diesel_entrega": 0,
          "diesel_depois": 100,
          "agua_antes": 150,
          "agua_entrega": 0,
          "agua_depois": 150
        },
        {
          "tipo": "visita",
          "no": 2,
          "nome": "P-09_order_2",
          "plataforma": "P-09",
          "deck_antes": 220,
          "deck_coleta": 0,
          "deck_pico": 220,
          "deck_entrega": 120,
          "deck_depois": 100,
          "diesel_antes": 100,
          "diesel_entrega": 0,
          "diesel_depois": 100,
          "agua_antes": 150,
          "agua_entrega": 0,
          "agua_depois": 150
        },
        {
          "tipo": "visita",
          "no": 3,
          "nome": "P-43_order_3",
          "plataforma": "P-43",
          "deck_antes": 100,
          "deck_coleta": 0,
          "deck_pico": 100,
          "deck_entrega": 80,
          "deck_depois": 20,
          "diesel_antes": 100,
          "diesel_entrega": 100,
          "diesel_depois": 0,
          "agua_antes": 150,
          "agua_entrega": 150,
          "agua_depois": 0
        }
      ],
      "segmentos": [
        {
          "tipo": "nav",
          "ini": 0.0,
          "fim": 6.0
        },
        {
          "tipo": "espera",
          "ini": 6.0,
          "fim": 8.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-09",
          "ini": 8.0,
          "fim": 9.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-09",
          "ini": 9.0,
          "fim": 11.0
        },
        {
          "tipo": "nav",
          "ini": 11.0,
          "fim": 16.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-43",
          "ini": 16.0,
          "fim": 19.0
        },
        {
          "tipo": "nav",
          "ini": 19.0,
          "fim": 30.0
        }
      ],
      "visitas": [
        {
          "no": 1,
          "nome": "P-09_order_1",
          "plataforma": "P-09",
          "chegada": 6.0,
          "ini": 8.0,
          "fim": 9.0,
          "espera": 2.0,
          "janela": [
            8.0,
            24.0
          ],
          "jidx": 0,
          "janelas": [
            [
              8.0,
              24.0
            ],
            [
              32.0,
              48.0
            ]
          ]
        },
        {
          "no": 2,
          "nome": "P-09_order_2",
          "plataforma": "P-09",
          "chegada": 9.0,
          "ini": 9.0,
          "fim": 11.0,
          "espera": 0.0,
          "janela": [
            8.0,
            24.0
          ],
          "jidx": 0,
          "janelas": [
            [
              8.0,
              24.0
            ],
            [
              32.0,
              48.0
            ]
          ]
        },
        {
          "no": 3,
          "nome": "P-43_order_3",
          "plataforma": "P-43",
          "chegada": 16.0,
          "ini": 16.0,
          "fim": 19.0,
          "espera": 0.0,
          "janela": [
            16.0,
            40.0
          ],
          "jidx": 0,
          "janelas": [
            [
              16.0,
              40.0
            ]
          ]
        }
      ],
      "navegacao_h": 22.0,
      "servico_h": 6.0,
      "espera_h": 2.0,
      "retorno_h": 30.0
    },
    {
      "k": 1,
      "nome": "STARNAV TAURUS2",
      "ocioso": false,
      "capacidades": {
        "deck": 360.0,
        "diesel": 260.0,
        "agua": 260.0
      },
      "carga_inicial": {
        "deck": 200.0,
        "diesel": 80.0,
        "agua": 180.0
      },
      "pico_deck": 235.0,
      "cargas": [
        {
          "tipo": "base",
          "nome": "Saida da base",
          "deck_depois": 200.0,
          "diesel_depois": 80.0,
          "agua_depois": 180.0
        },
        {
          "tipo": "visita",
          "no": 4,
          "nome": "P-51_order_4",
          "plataforma": "P-51",
          "deck_antes": 200,
          "deck_coleta": 35,
          "deck_pico": 235,
          "deck_entrega": 0,
          "deck_depois": 235,
          "diesel_antes": 80,
          "diesel_entrega": 0,
          "diesel_depois": 80,
          "agua_antes": 180,
          "agua_entrega": 0,
          "agua_depois": 180
        },
        {
          "tipo": "visita",
          "no": 5,
          "nome": "P-51_order_5",
          "plataforma": "P-51",
          "deck_antes": 235,
          "deck_coleta": 0,
          "deck_pico": 235,
          "deck_entrega": 140,
          "deck_depois": 95,
          "diesel_antes": 80,
          "diesel_entrega": 0,
          "diesel_depois": 80,
          "agua_antes": 180,
          "agua_entrega": 0,
          "agua_depois": 180
        },
        {
          "tipo": "visita",
          "no": 6,
          "nome": "P-40_order_6",
          "plataforma": "P-40",
          "deck_antes": 95,
          "deck_coleta": 0,
          "deck_pico": 95,
          "deck_entrega": 60,
          "deck_depois": 35,
          "diesel_antes": 80,
          "diesel_entrega": 80,
          "diesel_depois": 0,
          "agua_antes": 180,
          "agua_entrega": 0,
          "agua_depois": 180
        },
        {
          "tipo": "visita",
          "no": 7,
          "nome": "P-40_order_7",
          "plataforma": "P-40",
          "deck_antes": 35,
          "deck_coleta": 0,
          "deck_pico": 35,
          "deck_entrega": 0,
          "deck_depois": 35,
          "diesel_antes": 0,
          "diesel_entrega": 0,
          "diesel_depois": 0,
          "agua_antes": 180,
          "agua_entrega": 180,
          "agua_depois": 0
        }
      ],
      "segmentos": [
        {
          "tipo": "nav",
          "ini": 1.0,
          "fim": 9.0
        },
        {
          "tipo": "espera",
          "ini": 9.0,
          "fim": 10.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-51",
          "ini": 10.0,
          "fim": 11.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-51",
          "ini": 11.0,
          "fim": 12.5
        },
        {
          "tipo": "nav",
          "ini": 12.5,
          "fim": 20.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-40",
          "ini": 20.0,
          "fim": 22.5
        },
        {
          "tipo": "servico",
          "plataforma": "P-40",
          "ini": 22.5,
          "fim": 24.5
        },
        {
          "tipo": "nav",
          "ini": 24.5,
          "fim": 39.0
        }
      ],
      "visitas": [
        {
          "no": 4,
          "nome": "P-51_order_4",
          "plataforma": "P-51",
          "chegada": 9.0,
          "ini": 10.0,
          "fim": 11.0,
          "espera": 1.0,
          "janela": [
            10.0,
            28.0
          ],
          "jidx": 0,
          "janelas": [
            [
              10.0,
              28.0
            ],
            [
              52.0,
              74.0
            ]
          ]
        },
        {
          "no": 5,
          "nome": "P-51_order_5",
          "plataforma": "P-51",
          "chegada": 11.0,
          "ini": 11.0,
          "fim": 12.5,
          "espera": 0.0,
          "janela": [
            10.0,
            28.0
          ],
          "jidx": 0,
          "janelas": [
            [
              10.0,
              28.0
            ],
            [
              52.0,
              74.0
            ]
          ]
        },
        {
          "no": 6,
          "nome": "P-40_order_6",
          "plataforma": "P-40",
          "chegada": 20.0,
          "ini": 20.0,
          "fim": 22.5,
          "espera": 0.0,
          "janela": [
            20.0,
            46.0
          ],
          "jidx": 0,
          "janelas": [
            [
              20.0,
              46.0
            ]
          ]
        },
        {
          "no": 7,
          "nome": "P-40_order_7",
          "plataforma": "P-40",
          "chegada": 22.5,
          "ini": 22.5,
          "fim": 24.5,
          "espera": 0.0,
          "janela": [
            20.0,
            46.0
          ],
          "jidx": 0,
          "janelas": [
            [
              20.0,
              46.0
            ]
          ]
        }
      ],
      "navegacao_h": 30.0,
      "servico_h": 7.0,
      "espera_h": 1.0,
      "retorno_h": 39.0
    },
    {
      "k": 2,
      "nome": "STARNAV TAURUS3",
      "ocioso": false,
      "capacidades": {
        "deck": 280.0,
        "diesel": 180.0,
        "agua": 220.0
      },
      "carga_inicial": {
        "deck": 180.0,
        "diesel": 120.0,
        "agua": 90.0
      },
      "pico_deck": 205.0,
      "cargas": [
        {
          "tipo": "base",
          "nome": "Saida da base",
          "deck_depois": 180.0,
          "diesel_depois": 120.0,
          "agua_depois": 90.0
        },
        {
          "tipo": "visita",
          "no": 8,
          "nome": "P-38_order_8",
          "plataforma": "P-38",
          "deck_antes": 180,
          "deck_coleta": 25,
          "deck_pico": 205,
          "deck_entrega": 0,
          "deck_depois": 205,
          "diesel_antes": 120,
          "diesel_entrega": 0,
          "diesel_depois": 120,
          "agua_antes": 90,
          "agua_entrega": 0,
          "agua_depois": 90
        },
        {
          "tipo": "visita",
          "no": 9,
          "nome": "P-38_order_9",
          "plataforma": "P-38",
          "deck_antes": 205,
          "deck_coleta": 0,
          "deck_pico": 205,
          "deck_entrega": 110,
          "deck_depois": 95,
          "diesel_antes": 120,
          "diesel_entrega": 0,
          "diesel_depois": 120,
          "agua_antes": 90,
          "agua_entrega": 90,
          "agua_depois": 0
        },
        {
          "tipo": "visita",
          "no": 10,
          "nome": "P-55_order_10",
          "plataforma": "P-55",
          "deck_antes": 95,
          "deck_coleta": 0,
          "deck_pico": 95,
          "deck_entrega": 70,
          "deck_depois": 25,
          "diesel_antes": 120,
          "diesel_entrega": 120,
          "diesel_depois": 0,
          "agua_antes": 0,
          "agua_entrega": 0,
          "agua_depois": 0
        }
      ],
      "segmentos": [
        {
          "tipo": "nav",
          "ini": 2.0,
          "fim": 10.0
        },
        {
          "tipo": "espera",
          "ini": 10.0,
          "fim": 12.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-38",
          "ini": 12.0,
          "fim": 13.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-38",
          "ini": 13.0,
          "fim": 15.0
        },
        {
          "tipo": "nav",
          "ini": 15.0,
          "fim": 30.0
        },
        {
          "tipo": "servico",
          "plataforma": "P-55",
          "ini": 30.0,
          "fim": 32.5
        },
        {
          "tipo": "nav",
          "ini": 32.5,
          "fim": 50.0
        }
      ],
      "visitas": [
        {
          "no": 8,
          "nome": "P-38_order_8",
          "plataforma": "P-38",
          "chegada": 10.0,
          "ini": 12.0,
          "fim": 13.0,
          "espera": 2.0,
          "janela": [
            12.0,
            34.0
          ],
          "jidx": 0,
          "janelas": [
            [
              12.0,
              34.0
            ]
          ]
        },
        {
          "no": 9,
          "nome": "P-38_order_9",
          "plataforma": "P-38",
          "chegada": 13.0,
          "ini": 13.0,
          "fim": 15.0,
          "espera": 0.0,
          "janela": [
            12.0,
            34.0
          ],
          "jidx": 0,
          "janelas": [
            [
              12.0,
              34.0
            ]
          ]
        },
        {
          "no": 10,
          "nome": "P-55_order_10",
          "plataforma": "P-55",
          "chegada": 30.0,
          "ini": 30.0,
          "fim": 32.5,
          "espera": 0.0,
          "janela": [
            30.0,
            60.0
          ],
          "jidx": 0,
          "janelas": [
            [
              30.0,
              60.0
            ]
          ]
        }
      ],
      "navegacao_h": 41.0,
      "servico_h": 5.5,
      "espera_h": 2.0,
      "retorno_h": 50.0
    },
    {
      "k": 3,
      "nome": "STARNAV TAURUS4",
      "ocioso": true,
      "capacidades": {
        "deck": 320.0,
        "diesel": 220.0,
        "agua": 280.0
      },
      "carga_inicial": {
        "deck": 0.0,
        "diesel": 0.0,
        "agua": 0.0
      },
      "pico_deck": 0.0,
      "cargas": [],
      "segmentos": [],
      "visitas": [],
      "navegacao_h": 0.0,
      "servico_h": 0.0,
      "espera_h": 0.0,
      "retorno_h": 0.0
    }
  ]
};
