# Versionamento do SOKOL

Número canônico: arquivo `VERSION` na raiz (hoje **0.8.2**).

O SOKOL ainda não é 1.0. **1.0.0** só se declara quando o produto funciona
por completo — sem atalhos, sem filas no meio, sem UI e API dessincronizadas.
Até lá, cada release é 0.x.y.

## Quando subir a versão

**Só quando o operador pedir** («mude a versão», «bump», «sobe a versão»).

Não subir automaticamente depois de um fix, feature ou refactor. Terminar o
trabalho na versão em que começou.

Quando pedirem o bump, avaliar o **conjunto de alterações desde o último
número** (não só o último commit) e aplicar SemVer:

| Tipo | Sobe | Exemplos |
|------|------|----------|
| **PATCH** `0.8.2` → `0.8.3` | correção, copy, estilo, docs, rebuild | bug do proxy nginx, typo no README |
| **MINOR** `0.8.2` → `0.9.0` | capacidade nova, compatível | ingestão pela UI, subpastas no inbox, aba nova |
| **MAJOR** `0.x` → `1.0.0` | só quando o operador disser que está pronto / «tudo funciona» | não usar 2.0 enquanto estivermos em 0.x, salvo pedido explícito |

Em 0.x, MINOR pode incluir mudanças que em 1.x seriam breaking; mesmo assim
não saltar para 1.0.0 sem pedido.

## O que atualizar no bump

Tudo tem de ficar o mesmo número:

- `VERSION`
- `api/src/sokol/version.py`
- `web/src/lib/version.ts`
- `web/package.json` e o `"version"` do pacote em `web/package-lock.json`
- `api/pyproject.toml`, `db/pyproject.toml`, `services/*/pyproject.toml`
- `SOKOL_VERSION` / `version=` nos `services/*/src/main.py`
- menção «versão atual» em `README.md` e `CLAUDE.md` (estado atual)

Não mexer em `docs/archive/`, `PLANO_NOVO.md`, versões de dependências npm/PyPI,
nem na versão do Cellebrite no UFDR sintético.

## Onde aparece na UI

Rodapé do `AppShell` (`SOKOL v0.8.2`) e tela de login. `/health` da API devolve
o mesmo `version`.
