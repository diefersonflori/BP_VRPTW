"""
parse_construtiva.py
Lê o output do console da main.py (modo construtiva) e gera um placar resumido.
Uso: python main.py 2>&1 | python parse_construtiva.py
  ou: python main.py > output.txt 2>&1 && python parse_construtiva.py output.txt
"""
import sys
import re
from collections import defaultdict

def parse(lines):
    resultados = []
    inst_atual = None
    tam_atual = None
    n_art = None
    vencedor = None

    for line in lines:
        line = line.rstrip()

        # Detectar instância
        m = re.search(r'INSTANCIA=(\S+)', line)
        if m:
            inst_atual = m.group(1)
            # Extrair nome base
            nome = inst_atual.split('/')[-1].replace('.txt','').lower()
            inst_atual = nome
            n_art = None
            vencedor = None

        # Detectar tamanho
        m = re.search(r'tam=(\d+)', line)
        if m:
            tam_atual = int(m.group(1))

        # Detectar resultado da construtiva
        m = re.search(r'\[CONSTRUTIVA\] VENCEDOR: (.+)', line)
        if m:
            texto = m.group(1)
            if 'nenhuma rota artificial' in texto:
                n_art = 0
            else:
                # Pegar o menor número de artificiais entre Inteligente e CW
                arts = re.findall(r'(\d+) art', texto)
                if arts:
                    n_art = min(int(x) for x in arts)
                else:
                    n_art = 0
            vencedor = texto

            resultados.append({
                'inst': inst_atual,
                'tam': tam_atual,
                'n_art': n_art,
                'vencedor': vencedor,
            })

    return resultados

def familia(nome):
    if nome and nome.startswith('rc'):
        return 'RC'
    if nome and nome.startswith('r'):
        return 'R'
    return 'C'

def resumir(resultados):
    print("\n" + "="*70)
    print("PLACAR DA HEURÍSTICA CONSTRUTIVA")
    print("="*70)

    por_tam = defaultdict(list)
    for r in resultados:
        por_tam[r['tam']].append(r)

    total_ok = 0
    total_all = 0

    for tam in sorted(por_tam.keys()):
        grupo = por_tam[tam]
        print(f"\n── {tam} CLIENTES ({'='*40})")

        por_fam = defaultdict(list)
        for r in grupo:
            por_fam[familia(r['inst'])].append(r)

        tam_ok = 0
        for fam in ['C', 'R', 'RC']:
            if fam not in por_fam:
                continue
            itens = por_fam[fam]
            ok = [r for r in itens if r['n_art'] == 0]
            fail = [r for r in itens if r['n_art'] > 0]
            print(f"  {fam:3s}: {len(ok)}/{len(itens)} sem artificial", end="")
            if fail:
                nomes_fail = [r['inst'] for r in fail]
                print(f"  ❌ falhou: {nomes_fail}", end="")
            print()
            tam_ok += len(ok)

        tam_all = len(grupo)
        print(f"  SUBTOTAL {tam} clientes: {tam_ok}/{tam_all}")
        total_ok += tam_ok
        total_all += tam_all

    print(f"\n{'='*70}")
    pct = total_ok/total_all*100 if total_all else 0
    status = "✅ PERFEITO!" if total_ok == total_all else f"⚠️  {total_all - total_ok} casos com artificial"
    print(f"TOTAL GERAL: {total_ok}/{total_all}  ({pct:.1f}%)  {status}")
    print("="*70)

    # Listar falhas detalhadas
    falhas = [r for r in resultados if r['n_art'] > 0]
    if falhas:
        print("\nDETALHE DAS FALHAS:")
        for r in falhas:
            print(f"  {r['inst']:20s} tam={r['tam']}  n_art={r['n_art']}  {r['vencedor']}")

def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    resultados = parse(lines)

    if not resultados:
        print("Nenhum resultado encontrado. Verifique se o output contém linhas [CONSTRUTIVA].")
        return

    resumir(resultados)

if __name__ == '__main__':
    main()
