TRANSFORMADOR DE INSTANCIAS SILVA 2024 -> JSON BP_VRPTW

1) Converter a pasta inteira:
python transformador_instancias_silva.py "C:\Users\PolyanaSilva\Downloads\000_ALL_INSTANCES_PSVRP" -o "C:\Users\PolyanaSilva\Documents\BP_VRPTW\instancias\Petro_instancias\silva2024"

2) Para gravar alphaWeight=0 (ex.: validacao da Tabela 3):
python transformador_instancias_silva.py "C:\Users\PolyanaSilva\Downloads\000_ALL_INSTANCES_PSVRP" -o "C:\Users\PolyanaSilva\Documents\BP_VRPTW\instancias\Petro_instancias\silva2024" --alpha 0

3) Converter apenas uma instancia:
python transformador_instancias_silva.py "C:\Users\PolyanaSilva\Downloads\000_ALL_INSTANCES_PSVRP\14n-2k-6c-008r_ML.txt" --alpha 0

Saida:
<nome_original>_silva2024.json

O script ignora arquivos que comecam com 000_, como 000_README.txt.

MAPEAMENTO PRINCIPAL
DCP -> deckCargoBackload
DCD -> deckCargoLoad
DD  -> dieselLoad
WD  -> waterLoad
DC  -> deckSpace
D   -> dieselTanks
W   -> waterTanks
FCA/FCB/FCN/FCS -> fuelCost anchored/base/navigation/dynamic
SPO -> safePositioningTime
SET -> platformSetup
ETR -> estimatedTimeOfReadiness
TDL -> tripDurationLimit
TRI -> maximumNumberOfTrips
ET/LT -> timeWindows
Deadline -> dueTime

IMPORTANTE
Os campos *_Ef do arquivo Silva estao em horas/unidade. O JSON do projeto usa
"efficiency" em unidade/hora, porque o leitor calcula tempo = quantidade/efficiency.
Por isso o conversor grava efficiency = 1 / *_Ef.

Campos etaConversion, dieselDensity e conversionTonDieselTonCO2Eq sao mantidos
somente para compatibilidade com o schema Petrobras. Eles nao sao dados do benchmark Silva.
