import math
import json

class Veiculo:
    def __init__(self, capacidade=0, velocidade=0.0):
        self.capacidade = capacidade
        self.velocidade = velocidade


class Node:
    def __init__(self, node_id=0, x=0, y=0, demanda=0):
        self.id = node_id
        self.XCOORD = x
        self.YCOORD = y
        self.DEMAND = demanda
        self.READY_TIME = []
        self.DUE_DATE = []
        self.SERVICE_TIME = []


class Instancia:
    def __init__(self):
        self.nbv = 0  # Number of vehicles
        self.nbn = 0  # Number of nodes (clients + depots)
        self.nbcd = 0  # Number of clients
        self.noh = []  # List of Node objects
        self.matriz_distancia = []  # Distance matrix
        self.veiculos = []  # List of Veiculo objects
        self.fileName = ""
        #para teste com muitas
        self.ninst=0
        self.nbconstrutiva=0

    def leitura(self, argv):
        """

        with open("solucao_ex.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_gcm.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_gc.json", 'w') as f:
            json.dump("", f, indent=0)

        with open("solucao_final.json", 'w') as f:
            json.dump("", f, indent=0)
        """

        if len(argv) < 2:
            print("Error! File Name missing")
            exit(1)

        #"""
        #self.nbcd = 13
        #Q = 110
        #self.nbcd = 7
        #Q = 70
        #self.nbv = 2
        #"""
        #self.nbcd = 20
        #self.nbv = 2
        #Q = 200
        """
        #self.nbcd = 20
        #self.nbv = 2
        """

        #Q = 200
        """

        self.nbcd = 25
        self.nbv = 3
        Q = 200
        """

        """

        self.nbcd = 50
        self.nbv = 25
        Q = 1000
        """

        #self.nbcd = 4
        #Q = 36

        #self.nbn = self.nbcd + 2
        Vel = 1
        #Vel = 1
        self.fileName = argv

        with open(self.fileName, 'r') as infile:
            lines = infile.readlines()

        self.noh = [Node() for _ in range(self.nbn)]
        found = False
        idx = 0
        for i, line in enumerate(lines):
            if "TIME" in line:
                found = True
                for j in range(self.nbn - 1):  # nbn-1 nodes before final depot
                    parts = lines[i + j + 2].split()
                    #parts = lines[i + j + 1].split() ## ajuste para instancias em geral
                    #if len(parts) < 10:
                    #    continue  # Skip invalid lines
                    no_aux = Node(
                        node_id=int(parts[0]),
                        x=int(parts[1]),
                        y=int(parts[2]),
                        demanda=int(parts[3]),
                    )
                    a1 = int(parts[4])
                    a2 = int(parts[5])
                    #a3 = int(parts[6])
                    #a4 = int(parts[7])
                    #a5 = int(parts[8])
                    a5 = int(parts[6])
                    #a5 = int(parts[8])
                    #a6 = int(parts[9])
                    no_aux.READY_TIME.append(a1)
                    no_aux.DUE_DATE.append(a2)
                    #no_aux.READY_TIME.append(a3)
                    #no_aux.DUE_DATE.append(a4)
                    no_aux.SERVICE_TIME.append(a5)
                    #no_aux.SERVICE_TIME.append(90)
                    #$talvez colocar depois o servico
                    self.noh[j] = no_aux
                self.noh[self.nbn - 1] = Node(
                    node_id=self.nbn - 1,
                    x=self.noh[0].XCOORD,
                    y=self.noh[0].YCOORD,
                    demanda=self.noh[0].DEMAND
                )
                self.noh[self.nbn - 1].READY_TIME = list(self.noh[0].READY_TIME)
                self.noh[self.nbn - 1].DUE_DATE = list(self.noh[0].DUE_DATE)
                self.noh[self.nbn - 1].SERVICE_TIME = list(self.noh[0].SERVICE_TIME)

                break

        # Distância
        self.gera_matriz_distancias()
        # Veículos
        for jk in range(self.nbv):
            veic_aux = Veiculo(
                #capacidade=int(Q / (jk + 1)),
                #velocidade=int(Vel * (jk + 1))
                #capacidade = Q,
                capacidade = 0,
                velocidade = Vel
            )
            self.veiculos.append(veic_aux)

    def gera_matriz_distancias(self):
        self.matriz_distancia = [[0] * self.nbn for _ in range(self.nbn)]
        for i in range(self.nbn):
            for j in range(self.nbn):
                if i != j:
                    self.matriz_distancia[i][j] = self.calculo_distancia(
                        1,
                        self.noh[i].XCOORD, self.noh[i].YCOORD,
                        self.noh[j].XCOORD, self.noh[j].YCOORD
                    )
                else:
                    self.matriz_distancia[i][j] = -1

    def calculo_distancia(self, cond, cordx1, cordy1, cordx2, cordy2):
        if cond == 1:
            return math.hypot(cordx1 - cordx2, cordy1 - cordy2)
        return 0.0
