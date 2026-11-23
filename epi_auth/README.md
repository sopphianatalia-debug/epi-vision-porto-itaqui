# epi_auth — login e perfis (porta 8006)

Usuários com perfil **OPERADOR** ou **SUPERVISOR**. Quem entra recebe um token (JWT HS256, 8 h) que os outros serviços verificam com o **mesmo segredo** (`EPI_JWT_SECRET`, mínimo 16 caracteres, nunca no Git).

| Perfil | Pode |
|---|---|
| OPERADOR | entrar, ver e revisar incidentes; **não** sobrescreve a revisão de outra pessoa |
| SUPERVISOR | tudo do operador + mudar revisão de outros + gerenciar usuários |

## Rodar
```
export EPI_JWT_SECRET='um-segredo-longo-e-aleatorio'      # o MESMO nos outros serviços
export AUTH_DB_PATH=./auth.db                             # sem isso, usuários somem ao reiniciar
python -m app.cli create-user --username ana --name "Ana Lima" --role SUPERVISOR   # pede a senha sem mostrar
uvicorn app.main:app --port 8006
```
Para demonstração: `AUTH_DEMO_USERS=1` cria `operador` e `supervisor` com **senha aleatória mostrada uma vez no console** (só se o banco estiver vazio). Não há senha padrão no código.

## API (`/api/v1`)
`POST /auth/login` · `GET /auth/me` · `GET/POST /users` · `PATCH /users/{u}/active` · `PUT /users/{u}/password` (usuários: só supervisor).

## Segurança (o que está e o que não está)
- Senha com `scrypt` + sal; nunca em texto. Mensagem única para usuário inexistente ou senha errada (e mesmo tempo de resposta).
- 5 erros seguidos bloqueiam o usuário por 60 s (`AUTH_MAX_FAILED_LOGINS`, `AUTH_LOCK_SECONDS`).
- Token expirado, de outro emissor, de outro segredo ou com algoritmo `none` é recusado. Usuário desativado perde o acesso na hora (o token é conferido no banco).
- Não há desativar o próprio usuário nem o último supervisor ativo.
- **Pendente:** HTTPS (obrigatório fora do laboratório: sem ele a senha trafega aberta), recuperação de senha por e-mail, 2º fator, revogação de token antes do vencimento além de desativar o usuário.
