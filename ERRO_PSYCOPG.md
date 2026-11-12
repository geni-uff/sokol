# Erro `No module named 'psycopg'` e tela `Cannot GET /`

Este guia resolve dois problemas que aparecem ao subir o SOKOL no Windows (Ubuntu dentro do WSL2):

1. O container `sokol-api` não sobe. No log aparece:
   `ModuleNotFoundError: No module named 'psycopg'`
2. A API sobe, mas `http://localhost:3000` mostra só `Cannot GET /`.

Siga as partes na ordem. Todos os comandos são digitados no **terminal do Ubuntu**, a não ser quando o texto disser outra coisa.

---

## Por que isso acontece

**Erro do psycopg.** O SOKOL usa uma biblioteca chamada SQLAlchemy para falar com o banco de dados. Saiu uma versão nova dela que passou a pedir outro "conector" do banco (o `psycopg`), que o SOKOL não instala. Quem montou o SOKOL antes da versão nova não viu o erro. Quem montou depois, viu. A correção já está no código: o SOKOL agora usa sempre a versão antiga, que funciona.

**Tela `Cannot GET /`.** Essa mensagem não é do SOKOL. Ela aparece quando **outro programa** do Windows já está usando a porta 3000. O navegador abre esse outro programa em vez do SOKOL. A solução é mudar o SOKOL para outra porta.

---

## Parte 1: atualizar o código

### 1.1 Entre na pasta do SOKOL

```bash
cd ~/sokol
```

### 1.2 Desfaça a mudança feita à mão no Dockerfile

Se alguém acrescentou `psycopg>=3.3.8` no arquivo `api/Dockerfile`, essa mudança vai atrapalhar a atualização. Desfaça:

```bash
git checkout -- api/Dockerfile
```

Esse comando só volta o arquivo ao original. Ele **não** apaga seus dados, casos ou o arquivo `.env`.

### 1.3 Baixe a versão nova

```bash
git pull
```

### 1.4 Confira se a correção chegou

```bash
grep "sqlalchemy>=2.0,<2.1" api/Dockerfile
```

- **Apareceu uma linha?** Tudo certo. Vá para a Parte 2.
- **Não apareceu nada?** A correção ainda não foi publicada no GitHub. Avise o responsável pelo SOKOL e espere antes de continuar.
- **O `git pull` deu erro** (fala em `conflict`, `overwritten` ou `diverged`)? Use o plano B logo abaixo.

### Plano B: baixar tudo de novo (só se o `git pull` falhar)

Aqui vamos **renomear** a pasta antiga, sem apagar nada, e baixar uma cópia limpa. Depois trazemos de volta suas configurações e seus dados.

1. Pare o SOKOL:

```bash
cd ~/sokol/deploy
docker compose --env-file ../.env down
cd ~
```

> Esse `down` não apaga o banco de dados. Os casos continuam guardados.

2. Renomeie a pasta antiga:

```bash
mv ~/sokol ~/sokol_antigo
```

3. Baixe a cópia nova:

```bash
git clone https://github.com/geni-uff/sokol.git
cd ~/sokol
```

4. Traga de volta a configuração e as pastas de dados:

```bash
cp ~/sokol_antigo/.env ~/sokol/.env
cp -r ~/sokol_antigo/data ~/sokol/ 2>/dev/null
cp -r ~/sokol_antigo/UFDRsTest ~/sokol/ 2>/dev/null
cp -r ~/sokol_antigo/ingest ~/sokol/ 2>/dev/null
```

Se alguma dessas pastas não existir, o comando não faz nada. Pode seguir.

5. Repita o passo 1.4 para conferir.

6. **Só apague a pasta antiga depois** que o SOKOL estiver funcionando (fim da Parte 4):

```bash
rm -rf ~/sokol_antigo
```

---

## Parte 2: descobrir se a porta 3000 está ocupada

Esta parte é feita no **Windows**, não no Ubuntu.

1. Pare o SOKOL antes, no Ubuntu:

```bash
cd ~/sokol/deploy
docker compose --env-file ../.env down
```

2. No Windows, abra o menu Iniciar, digite `PowerShell` e abra.
3. Digite:

```powershell
netstat -ano | findstr :3000
```

- **Não apareceu nada:** a porta está livre. Pule para a Parte 4.
- **Apareceu alguma linha com `LISTENING`:** outro programa está usando a porta 3000. O último número da linha é o código do programa (PID). Se quiser saber qual é, abra o Gerenciador de Tarefas (Ctrl + Shift + Esc), vá em **Detalhes** e procure esse número na coluna **PID**. Siga para a Parte 3.

---

## Parte 3: mudar o SOKOL para a porta 3001

Volte para o **terminal do Ubuntu**.

1. Abra o arquivo de configuração:

```bash
cd ~/sokol
nano .env
```

2. Procure a linha que começa com `SOKOL_WEB_PORT=`. Use as setas do teclado para andar.
3. Troque o número para `3001`. A linha deve ficar assim:

```
SOKOL_WEB_PORT=3001
```

Se a linha não existir, escreva-a no final do arquivo.

4. Salve e saia:
   - aperte **Ctrl + O** e depois **Enter** (salva);
   - aperte **Ctrl + X** (sai).

---

## Parte 4: subir o SOKOL de novo

```bash
cd ~/sokol
bash ops/start-sokol.sh
```

Na primeira vez depois da correção vai demorar mais, porque o Docker monta a API de novo. Espere até aparecer a mensagem `SOKOL no ar:` com o endereço.

### Confira

1. A API responde:

```bash
curl http://localhost:8000/health
```

Deve aparecer algo com `"status":"ok"`.

2. No **navegador do Windows**, abra o endereço que o script mostrou:
   - `http://localhost:3000`, se você não mudou a porta;
   - `http://localhost:3001`, se você fez a Parte 3.

Deve aparecer a tela de login do SOKOL. Usuário `admin`, senha `admin123`.

---

## Se ainda der erro

Copie a saída destes comandos e mande para o responsável pelo SOKOL:

```bash
cd ~/sokol
git log -1 --oneline
docker ps -a
docker logs sokol-api 2>&1 | tail -n 40
docker logs sokol-web 2>&1 | tail -n 20
```
