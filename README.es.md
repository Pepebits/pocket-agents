<p align="center"><img src="docs/banner.png" alt="pocket-agents" width="720"></p>

<p align="center"><em><a href="README.md">English</a> · Español</em></p>

VPS de **desarrollo remoto** para Claude Code: sesiones persistentes, una por proyecto,
controlables desde el móvil o el navegador sin tener el ordenador encendido.

Ubuntu 24.04. Script idempotente en dos fases.

```bash
ssh root@<IP> 'bash -s' < setup.sh     # fase 1 — base del sistema
ssh dev@<IP>  'bash -s' < setup.sh     # fase 2 — toolchains, Claude, proyectos
```

La fase se detecta sola según quién lo ejecute. Relanzarlo no rompe nada.

### Configuración

No hay nada personal fijado en el código. Los ajustes van en un `config.env` que git
ignora —copia [`config.env.example`](config.env.example), que documenta cada uno— y se
pone delante del script:

```bash
cp config.env.example config.env    # y lo editas
cat config.env setup.sh | ssh dev@<IP> 'bash -s'
```

Es la única vía: `setup.sh` llega por `bash -s`, así que no puede preguntarte nada, y
ssh no lleva tus variables locales al servidor — un `REPOS=... ssh ...` no llega nunca.

## Documentación visual

**[Abrir la página](https://pepebits.github.io/pocket-agents/overview.html)** ([código](docs/overview.html)) — página autocontenida con los diagramas del
montaje: la topología (por qué tu portátil sale del camino), la cadena de supervisión
(systemd → tmux → claude, y qué papel juega `enable-linger`), el fallo del socket tmux
en before/after, y el recorrido del código de login por Telegram. Ábrela en cualquier navegador; no depende de nada externo salvo las
fuentes de Google.

## Qué monta

**Fase 1 (root)** — usuario `dev` con las claves SSH de root, login de root y por
contraseña desactivados (borra también el override de cloud-init que los reactiva),
ufw con solo el 22 abierto, fail2ban, swap de 4 GB con `swappiness=10`, journald capado
a 500 MB, Docker Engine con GC del build cache a 5 GB y rotación de logs, y
`enable-linger` para que los servicios de usuario sobrevivan al cierre de sesión.

**Fase 2 (dev)** — [mise](https://mise.jdx.dev) con node LTS / go 1.23 / python 3.12 /
rust / uv, Claude Code en user-space (sin `sudo`), las herramientas de `bin/` instaladas
en `~/.local/bin`, la plantilla `claude@.service` y un `~/.claude/settings.json`
restrictivo. Con `CODEX=1`, además el Codex de OpenAI y su unidad — apagado por defecto,
porque instala desde un canal propio que se auto-actualiza y su alta no termina sin dos
ajustes en una cuenta de ChatGPT que el script no puede tocar.

El script **no clona ningún repo por su cuenta**: la lista nace vacía y la eliges tú.

## Uso

Después de la fase 2, elige qué repos se convierten en sesiones:

```bash
claude-repos pick      # lista tus repos de GitHub y GitLab, eliges por número
claude-repos list      # qué hay configurado y qué está levantado
claude-repos add gitlab:grupo/repo
```

Necesita un terminal de verdad, así que va en una sesión SSH normal y no dentro de
`setup.sh` — ese llega por `bash -s`, su stdin *es* el propio script y no tiene por
dónde preguntar.

```bash
systemctl --user enable --now claude@<proyecto>   # a mano, si lo prefieres
ssh dev@<IP> -t tmux -L claude-<proyecto> attach -t claude-<proyecto>   # entrar en crudo
```

Cada proyecto de `~/dev/` se convierte en una sesión con nombre propio dentro de la app
de Claude. Ver [docs/runbook.md](docs/runbook.md) para el día a día y
[docs/troubleshooting.md](docs/troubleshooting.md) para los fallos ya diagnosticados.

## Reautenticación y vigilancia

Las sesiones desatendidas tienen un fallo que no se ve venir: **el refresh token de
OAuth es de un solo uso**. Cuando el access token caduca, cada sesión intenta refrescar
con su propia copia del mismo grant; gana una y las demás reciben un rechazo, ante el
cual Claude Code borra las credenciales guardadas. El proceso NO muere, así que
`Restart=on-failure` no se dispara: la sesión se queda viva y sin Remote Control hasta
que alguien lo nota.

`bin/` resuelve las dos mitades del problema — enterarse, y arreglarlo sin estar delante.
**La fase 2 lo instala todo**; esto es solo para actualizar a mano tras un `git pull`:

```bash
install -m755 bin/claude-* ~/.local/bin/
install -m644 systemd/*.service systemd/*.timer ~/.config/systemd/user/
install -Dm644 share/i18n.json ~/.local/share/claude-rc/i18n.json
```

**El bot se recarga solo**, y no por comodidad: instalar dejaba el fichero nuevo en su
sitio mientras el proceso seguía con el viejo en memoria, así que un botón recién
añadido *no existía* para él y la única pista era un giro que no hacía nada. Ahora
compara al final de cada vuelta el `mtime` y el tamaño de su propio fichero y de
`i18n.json` con los que cargó; si cambiaron, lo dice por Telegram y sale, y
`Restart=always` lo devuelve en diez segundos. No sale si lo de disco no compila:
`install` escribe *en sitio*, hay un instante con el fichero a medias, y una versión rota
daría un reinicio cada diez segundos para siempre. Las **unidades** siguen necesitando
`systemctl --user daemon-reload`.

Los mensajes salen en **inglés por defecto**; `CLAUDE_RC_LANG=es` los pone en español, y
los unit files ya lo traen. Las traducciones viven en `share/i18n.json`, compartido por
los cuatro scripts: añadir un idioma o corregir una cadena no toca código. Si el fichero
falta, los scripts siguen funcionando y los mensajes salen como claves.

| | |
|---|---|
| `claude-rc-status` | Estado real de cada sesión: credenciales en disco y `bridgeSessionId`, no el panel |
| `claude-login-bridge` | Hace el `/login` interactivo por Telegram: manda el enlace, recibe el código, lo teclea |
| `claude-rc-bot` | Único consumidor de `getUpdates`; pasa el código al puente por fichero |
| `claude-rc-watchdog` | Enlace caído, login que caduca, reinicio pendiente y puertos expuestos |
| `claude-session` | Reemplaza el `ExecStart`: siembra la confianza del workspace y reanuda con `--continue` |
| `claude-repos` | Elige repos de GitHub y GitLab y los convierte en sesiones |
| `claude-docker-gc` | Barrido diario del disco: techo al build cache, capas sueltas, contenedores viejos |

**Cómo se sabe si una sesión está conectada.** No por el panel: la píldora `/rc` de la
barra se recorta en un pane estrecho aunque el puente esté vivo, y aparece por
auto-activación aunque no se pida `--remote-control`. La señal buena es
`bridgeSessionId` en `~/.claude-<sesión>/sessions/<pid>.json`, que Claude escribe al
montar el puente. Un diálogo bloqueante se detecta por **presencia** de su texto, nunca
por ausencia de otra cosa.

El puente y el bot necesitan un bot de Telegram propio:

```bash
install -d -m700 ~/.config/claude-rc-telegram
cat > ~/.config/claude-rc-telegram/config <<'EOF'
TG_TOKEN=<el token que te da @BotFather>
TG_CHAT=<tu user id numérico>
EOF
chmod 600 ~/.config/claude-rc-telegram/config
systemctl --user enable --now claude-rc-bot
```

```bash
claude-rc-bot --setup    # una vez: publica el menú y las descripciones del bot
```

Desde el móvil: `/status`, `/login <sesión>`, `/new`, `/close <sesión>`, `/ports`,
`/backup`, `/disk`, `/reboot`, `/codex`, `/update`, y los mismos con botones. Los nombres de los comandos van siempre en inglés — son identificadores, como
`/status` y `/login` — y las descripciones se traducen; `/nueva` y `/cerrar` siguen
valiendo como alias.

`/new` tiene tres modos y desambigua con botones en vez de con sintaxis:

- `/new owner/repo` (con barra) clona directo.
- `/new nombre` pregunta: **clonar tu repo**, **crear repo privado** o **sesión vacía**.
  Si `~/dev/<nombre>` ya existe sin sesión, el único botón es *levantar tal cual*.

Los repos que crea son **siempre privados**, sin bandera para publicarlos: un repo
público por accidente no se deshace. Y nunca se borra un remoto al deshacer un alta a
medias; se dice que existe y que reintentar lo retoma.

Tras levantar, el bot mira el panel y dice si la sesión llegó al prompt, se quedó en un
diálogo o murió. **Solo queda el login a mano**: la confianza del workspace la siembra
`claude-session`, pero autenticar sigue siendo tuyo.

**⏸ Pausar / ▶️ Reanudar**, un botón por sesión. Cada sesión ocupa 0,5–1 GB, y con 8 GB
caben cuatro cómodas: pausar es `stop` y no `disable --now`, así que no cierra ni borra
nada —repo, config dir y conversación siguen donde estaban— y la unidad arranca con
`--continue`, o sea que reanudar la retoma en el mismo punto. El mensaje dice cuánta
memoria quedó libre, que es el motivo de pulsarlo. Una pausada sale ⏸ y no ⛔ porque lo
que las distingue es que `systemctl is-active` diga `inactive`, y con `Restart=always`
eso solo pasa si alguien la paró.

**`/backup` — trabajo que solo existe en este disco.** Una sesión que commitea sola
produce el fallo que nadie ve venir. Medido aquí el 2026-09-13: `QueueEngine` con 21
commits sin subir de hacía ocho días, y `finance-app` —una sesión **viva**— con el repo sin
remoto siquiera. Nada lo decía; el runbook mandaba mirarlo antes de un `rm -rf`, que es
justo cuando ya te acordabas. El bot lo comprueba una vez al día y avisa solo si hay algo,
con dos niveles porque son dos problemas: ⛔ no tiene dónde ir y eso no lo arregla un botón,
⚠️ lo tiene y no ha ido, y ahí el ⬆️ hace el `push`.

Dispara lo que **no se arregla esperando** —sin remoto, rama que no sigue a ninguna,
commits sin subir, stashes— con una gracia de 6 h sobre el más viejo, porque un commit de
hace cinco minutos no es trabajo abandonado. Los ficheros sin commitear **no** lo disparan
por sí solos: eso es una sesión trabajando, y una alarma que suena a diario por lo normal
acaba ignorándose. El `git push` sigue denegado a Claude; el botón lo pulsas tú, que es la
misma decisión deliberada tomada desde el móvil.

**`/reboot` — qué cuesta reiniciar ahora mismo.** `unattended-upgrades` instala los parches
de kernel y de libc pero no reinicia, a propósito. El resultado medido: 24 días de uptime
con `libc6` y dos kernels esperando. Lo que frena el reinicio no es el riesgo, es no saber
qué se pierde — y se pierde menos de lo que parece, porque los ficheros se quedan y cada
sesión vuelve con `--continue`. Lo único que se interrumpe es lo que un agente tenga **a
medias**, y eso se lee en la barra del panel. Reiniciar no es una operación de usuario: si
polkit no se la concede al bot, lo dice y te da el comando.

Con una trampa que costó una tanda de diagnóstico: **que exista el socket de tmux no
significa que haya nadie**. tmux deja el fichero atrás cuando el servidor muere, así que
un `exists()` pintaba las pausadas como vivas y el botón de Reanudar no aparecía jamás.
Lo que se pregunta ahora es si alguien lo *atiende*, con un `connect()` a la unix socket:
sin servidor da `ECONNREFUSED` al instante, y cuesta microsegundos.

El menú de comandos se publica en scope `chat` con tu id, así que un desconocido que abra
el bot no ve ni la lista. La lista es **estática a propósito**: los comandos son verbos y
las sesiones van en los botones inline. Meterlas en el menú obligaría a rellamar a la API
en cada alta y baja, y aun así los clientes lo cachean. Además un nombre de comando solo
admite minúsculas, dígitos y `_`, así que `mi-repo` y `mi.repo` colisionarían.

La API **no permite autocompletar argumentos**: elegir `/login` del menú lo envía a secas.
Por eso ese camino responde con los botones de sesión.

**Por qué un comando tardaba 47 segundos.** El `timeout` de `getUpdates` y el del socket
son dos cosas distintas, y confundirlas costaba eso: Telegram retiene la respuesta los
segundos que le pidas, pero si la conexión se muere en silencio —unas **80 veces al
día**, medido en el journal— el cliente no se entera hasta que salta *su* plazo, y
mientras tanto el botón que pulsaste sigue en el servidor sin que nadie lo recoja. Ahora
el socket va justo por encima del long-poll, con sondas de keepalive de TCP para que un
extremo muerto se detecte en ~11 s en vez de 25.

Y el bot es de un solo hilo a propósito, así que el segundo toque de un lote esperaba a
que terminase el trabajo del primero —Pausar y Reanudar tardan segundos— y para entonces
Telegram ya había caducado la pulsación: un botón girando sin fin. Se contesta a **todo
el lote** nada más recogerlo, y el mismo botón repetido cuenta como una intención, no
como tres.
Contestar un toque tiene su propio plazo de socket, 6 s, y un reintento, porque solo
sirve dentro de los ~15 s que vive una pulsación: una respuesta que tardó 36,5 s en
salir, con el plazo general de 45 s, llegó a un toque ya caducado. Y los cortes de red
del long-poll —un centenar al día, cada uno recuperado en la vuelta siguiente— se cuentan
en vez de apuntarse uno a uno: una línea si fallan tres seguidos, otra al volver, y un
resumen al día.

```bash
systemctl --user enable --now claude-rc-watchdog.timer
```

El vigilante hace dos cosas, y la preventiva es la que importa: **avisa por Telegram
cuando al login le quedan `WARN_DAYS` o menos** (3 por defecto), una vez al día por
sesión. Eso es lo único que ataca la causa — el incidente que originó todo esto se
habría evitado renovando a tiempo. Lo demás es reacción: detecta el enlace caído, avisa
como mucho una vez por hora, y reinicia tras tres comprobaciones fallidas.

El `.service` ya trae `MAX_RESTARTS=3` y `WARN_DAYS=3`. Ese tope no es paranoia: la
detección buscaba el texto en todo el panel, y como estas sesiones hablan de este mismo
sistema, dos sesiones **sanas** salían marcadas como caídas. Sin límite habría sido un
bucle de reinicios matando una conversación cada tres minutos. La detección ya solo mira
la barra de estado, pero el tope se queda.

`--dry-run` dice lo que haría sin reiniciar ni enviar nada.

Las variables de entorno de todos los scripts van en inglés: `SESSIONS`,
`MAX_RESTARTS`, `WARN_DAYS`, `FAILURES_BEFORE_RESTART`, `ATTEMPTS`, `URL_TIMEOUT`,
`CODE_TIMEOUT`. `SESSIONS` es solo un **respaldo** para cuando no hay instancias
habilitadas en systemd; no sirve para acotar, porque systemd es la fuente de verdad.

## El otro agente: Codex

Codex trae **su propio control remoto**, así que no se envuelve como Claude. Y su modelo
es el contrario: **un daemon con N hilos**, no N procesos con un config compartido. Todo
`claude@<proyecto>` —un servicio por repo, un servidor tmux por servicio, un
`CLAUDE_CONFIG_DIR` por sesión— nació de la carrera del `.claude.json`, y Codex no la
tiene. Aquí hay **una** unidad, no siete.

```bash
CODEX=1 sudo -E bash setup.sh     # instala el standalone y la unidad
```

**Los dos pasos que no dice ningún error** y que cuestan la tarde:

1. En los ajustes de ChatGPT, **habilitar la autorización por código de dispositivo para
   Codex**. Sin esto, `codex login --device-auth` se queda esperando y ya está.
2. **MFA activado en la cuenta.** El enrolamiento falla con
   `HTTP 403 · {"detail":"Multi-factor authentication required"}`, y eso solo se ve si
   miras la salida del `pair`.

Luego, **en este orden**:

```bash
codex login --device-auth                        # URL + código
systemctl --user enable --now codex-app-server   # DESPUÉS del login
codex remote-control pair                        # código de ~10 min
```

El servicio va después del login porque **el app-server no relee `auth.json`**: arrancado
sin credenciales dice `the connection is errored`, que suena a red y es «te has logueado
después». El bot lo reinicia solo cuando detecta que el login acaba de completarse.

Emparejar es **repetible**: cada llamada da un código nuevo de unos diez minutos, mientras
que el `environmentId` de la máquina no cambia. El código es un apretón de manos, no un
estado que guardes — pídelo las veces que haga falta.

Tiene que ser el **standalone**, no el paquete de npm: `codex app-server daemon` aborta
con `managed standalone Codex install not found`. Tener los dos es peor que ninguno,
porque gana el que diga el orden del `PATH` — que no es el mismo en tu shell que en las
units. El script quita el de npm si lo encuentra.

**La unidad corre el app-server real en primer plano**, no `codex app-server daemon
start`: ese lanza el proceso y sale, así que systemd se encontraría el cgroup vacío y
daría el servicio por terminado — el mismo fallo del socket de tmux que costó dos días
aquí. El precio es el auto-actualizador que trae el envoltorio; a cambio, la versión se
cambia a mano, igual que la de Claude.

Y `/codex` en el bot mira **tres cosas por separado** —servicio, app-server y login—
porque se arreglan de formas distintas, con botones de Parar, Arrancar, Reiniciar, Login y
Emparejar; solo aparece lo que se puede hacer ahora. El login por Telegram sale casi
gratis: `--device-auth` es de un solo sentido, así que el bot solo lee dos líneas, sin nada
del puente con fichero que necesita Claude.

**Actualizar es manual en los dos**, y también a propósito: `/update` compara lo instalado
con lo disponible y pregunta. Codex lo reinicia el bot solo —es un servicio sin
conversación que perder—, pero cada sesión de Claude conserva la versión con la que
arrancó y solo la coge al reiniciarla, lo cual interrumpe lo que tenga a medias. Esa
decisión sigue siendo tuya.

## Previews desde el móvil (opcional)

`cloudflare/tunnel-setup.sh` expone los servidores de desarrollo por HTTPS **sin abrir
ningún puerto entrante**: `cloudflared` sale hacia fuera igual que las sesiones de Claude.

```bash
cloudflared tunnel login     # una vez, elige la zona en el navegador
./tunnel-setup.sh            # crea el tunel, las rutas DNS y el servicio
```

La zona sale de `ZONE` en el `config.env` de la raíz del repo; si no está, el script la
pregunta, porque este sí se ejecuta a mano en una terminal.

Cada puerto de desarrollo queda en `p<puerto>-dev.<zona>`: levanta un `npm run dev` en
el 3000 y lo abres en `https://p3000-dev.<zona>` desde donde estés. El mapeo es por
puerto y no por proyecto, así cualquier cosa que arranques ya tiene URL sin tocar la
config del túnel.

> **Estas URLs son públicas** mientras el servidor esté levantado. Ponles Cloudflare
> Access delante (Zero Trust → Access → Applications, dominio `p*-dev.<zona>`, política
> `Emails` con tu correo). Sin eso, la única barrera es que nadie adivine el subdominio.

## Personalizar los repos

Lo normal es `claude-repos pick` después de la fase 2. Para automatizar, `REPOS` en
`config.env` acepta identificadores con forja:

```bash
REPOS="miorg/uno gitlab:migrupo/dos"
```

Sin prefijo es GitHub. La lista queda en `~/.config/claude-sessions/repos.conf`, que es
la fuente de verdad: un relanzamiento clona y levanta lo que falte, sin volver a
preguntar.

## Red y contenedores

**ufw no basta con Docker.** Docker escribe sus propias reglas y se evalúan *antes* que
las de ufw, así que un `-p 8080:80` descuidado abre el puerto a Internet aunque ufw lo
esté denegando. La fase 1 pone tres reglas en `DOCKER-USER` (vía `/etc/ufw/after.rules`,
para que sobrevivan a reinicios y a actualizaciones de Docker) que cortan todo lo
entrante desde la interfaz pública hacia cualquier contenedor, y bloquean el servicio de
metadatos del proveedor.

La política puede ser absoluta porque la vía pública es el túnel, que sale hacia fuera y
entra por loopback: **ningún contenedor necesita publicar en `0.0.0.0`**. Además
`daemon.json` lleva `"ip": "127.0.0.1"`, para que un `-p` sin dirección nazca atado a
loopback.

El vigilante avisa por Telegram si algo empieza a escuchar fuera de loopback y no está en
la lista blanca (`tcp:22`), distinguiendo si es un publish de Docker o un proceso nativo,
porque la respuesta es distinta.
Un proceso nativo solo lo dispara tras 15 minutos escuchando sin parar
(`CLAUDE_RC_NET_GRACE`, en segundos): ufw ya lo bloquea, y los servidores de tests que
cogen un puerto nuevo en cada tanda y mueren al acabarla fueron 45 de 47 avisos en once
días. Lo publicado por Docker avisa en el acto, porque Docker se salta ufw.

**El aviso lleva un botón 🔇 Silenciar**, y al pulsarlo el propio mensaje se convierte en
la confirmación y ofrece el 🔊 inverso: equivocarse se deshace sin salir de ahí. Antes era
acordarse de la ruta de un fichero y entrar por SSH, que en una máquina de desarrollo —un
preview de Vite, un binario en `target/debug`— no escala, y el resultado fue siete avisos
del mismo puerto en una tarde.

`/ports` es el inventario de lo que escucha, en tres grupos porque son tres situaciones y
solo una pide que hagas algo:

```
🔴 tcp:50051 — rust-booking-engine · 9 d          ← avisará hoy, con su 🔇
🟢 tcp:22 — abierto 🔒                            ← callado a mano, con el 🔊
· tcp:5173 — node vite dev --force · 4 h          ← solo 127.0.0.1: ni avisa ni puede
```

Detrás del puerto, quién lo sirve y cuánto lleva levantado. El 🔒 viene de
`CLAUDE_RC_NET_ALLOW` en la unidad y no del fichero, así que el bot no puede quitarlo.
Hacen falta `ss` **y** `docker ps` aunque parezca redundante: con el proxy en espacio de
usuario un puerto publicado sí sale en `ss`, pero como `docker-proxy` y corriendo como
root —un socket sin dueño—, y sin el proxy la publicación es DNAT puro y en `ss` no hay
nada que ver. Donde no se puede ver el proceso ajeno se calla el dueño en vez de
inventarlo.

También avisa cuando hay un reinicio pendiente:
`unattended-upgrades` instala los parches de kernel pero no reinicia a propósito —se
llevaría las sesiones—, así que sin ese aviso la máquina corre indefinidamente con un
kernel viejo.

Las versiones de runtime se pueden fijar desde fuera. `NODE_V` vale **24** —la LTS
vigente— y es un major fijo a propósito: dentro de esa línea siguen llegando parches,
pero el salto a la siguiente LTS lo decides tú. Con `lts` un relanzamiento futuro
cambiaría de major sin avisar, y eso rompe la promesa de que relanzar no rompe nada.

```bash
NODE_V=lts      # en config.env: seguir la LTS vigente
GO_V=1.24
```

**Esto solo fija la versión global.** Un proyecto que necesite otra la declara en su
propio repo con `.node-version`, `.nvmrc` o `.mise.toml`, y mise la respeta al entrar en
el directorio. Con una trampa que conviene conocer: si la versión pedida **no está
instalada**, mise no falla ni la instala — cae en silencio a la global. Comprobado en
este servidor. Así que al clonar un repo con pin propio, la primera vez:

```bash
cd ~/dev/<repo> && mise install
```

## Presupuesto de disco

Docker es lo que llena el disco, y no por donde parece. `claude-docker-gc` barre a diario
(timer con `RandomizedDelaySec=1h`): **techo de 4 GB al build cache**, capas sueltas,
contenedores parados de más de una semana y redes huérfanas.

Techo y no edad, y esto costó un barrido en blanco: el filtro `until` de BuildKit mira el
*último uso*, no cuándo se creó, así que una capa de hace tres semanas que un build tocó
ayer cuenta como nueva — con `until=336h` el primer barrido recuperó **0 B sobre 8,3 GB**.
Con el techo, BuildKit desaloja por orden de último uso y conserva el working set.

Lo que **no** hace, y no por olvido:

- **Volúmenes, jamás.** Un volumen inactivo es lo que queda entre un `compose down` y el
  siguiente `up` — la base de datos de alguien. `--volumes` no aparece en el script.
- **Imágenes etiquetadas sin usar.** Suelen ser el trozo más gordo (medido: 7,45 GB, el
  85 % del espacio de imágenes), pero solo caen con `-a`, y con ellas se van `php:8.4-cli`
  o `postgres:17-alpine`, que el siguiente build vuelve a bajar.

Una máquina no distingue «experimento de hace dos semanas» de «la base de mañana», así que
esas dos las decide una persona — y **`/disk` es donde se deciden**. Una imagen se va de un
toque, porque vuelve con un pull o un build; un volumen **pregunta antes** y enseña el
nombre, porque no vuelve. Antes esto solo aparecía si el disco pasaba del 75 %, y lleva
meses al 56 %: ese aviso no había sonado nunca.

Los botones **nunca repiten texto**, y eso es una corrección, no un detalle: quitándoles la
etiqueta para que entraran, `php:8.4-cli` y `php:8.3-cli` quedaban los dos en `🗑 php` —
dos botones idénticos con distinto efecto, que es exactamente como se borra lo que no
querías.

## Tests

```bash
./tests/run              # los herméticos: un Telegram y un HOME de mentira
./tests/run --live       # además los de diagnóstico, que leen el estado de esta máquina
```

Sin dependencias más allá de python3 y `git`. Ver [tests/README.md](tests/README.md).

## Principios

- **Sin contenedores.** Contenerizar Claude obliga a montarle el socket de Docker para
  que pueda usar compose y testcontainers, y eso equivale a darle root en el host: el
  aislamiento que justificaba el contenedor desaparece. Usuario dedicado + permisos
  restrictivos es más simple y no es menos seguro.
- **Separado de producción.** Este VPS no sirve nada público. Un experimento no puede
  tumbar un sitio.
- **Todo en user-space.** Claude se instala bajo `~/.local`, nunca con `sudo npm -g`.
- **Git como punto de encuentro.** El VPS y tu portátil son máquinas independientes;
  se sincronizan por git, no por rsync.
- **Nada que ejecute cosas arbitrarias en el allowlist.** `python3`, `make`, `npm run`,
  `uv run`, `mise` y `docker compose` están fuera a propósito. Con ellos dentro, negar
  `sudo` era decorativo: `python3 -c 'os.system("sudo …")'` no empieza por `sudo`, y con
  `NOPASSWD` eso es root sin un solo prompt. Y con `--permission-mode acceptEdits` el
  agente puede *escribir* primero el Makefile que luego ejecuta. El disparador realista
  no es el agente portándose mal, es una inyección de prompt: estas sesiones leen webs,
  issues y READMEs de dependencias. Ahora esas órdenes preguntan, y para eso está el
  control remoto en el móvil.
- **Detectar por presencia, no por ausencia.** Que no aparezca una señal no prueba nada:
  un pane estrecho la trunca y un subagente la empuja fuera de la ventana. Los dos
  falsos positivos que ha dado este sistema venían de deducir un estado de la falta de
  otro.
