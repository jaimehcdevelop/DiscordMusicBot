import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import os
import aiohttp
import edge_tts  # Librería de IA de voz neuronal

opciones_ytdl = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best',  # <-- Obliga a buscar m4a primero
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'ignoreerrors': True,
    'source_address': '0.0.0.0' # <-- Truco para evitar bloqueos de IP IPv6 en YouTube
}

opciones_ffmpeg = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 192k'
}

ytdl = yt_dlp.YoutubeDL(opciones_ytdl)

# --- CLASE DE BOTONES INTERACTIVOS ---
class ControlMusicaView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=None)
        self.cog, self.ctx = cog, ctx

    @discord.ui.button(label="Pausa / Reanudar", style=discord.ButtonStyle.blurple, emoji="⏯️")
    async def pausar_reanudar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cliente_voz = self.ctx.voice_client
        if not cliente_voz: return
        if cliente_voz.is_playing(): cliente_voz.pause()
        elif cliente_voz.is_paused(): cliente_voz.resume()

    @discord.ui.button(label="Saltar", style=discord.ButtonStyle.green, emoji="⏭️")
    async def saltar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.ctx.voice_client: self.ctx.voice_client.stop()

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🔀")
    async def mezclar(self, interaction: discord.Interaction, button: discord.ui.Button):
        id = self.ctx.guild.id
        if id in self.cog.colas and not self.cog.colas[id].empty():
            elementos = []
            while not self.cog.colas[id].empty():
                elementos.append(self.cog.colas[id].get_nowait())
            random.shuffle(elementos)
            for item in elementos:
                self.cog.colas[id].put_nowait(item)
            await interaction.response.send_message(f"🔀 **{interaction.user.display_name}** ha mezclado la cola ({len(elementos)} canciones).", ephemeral=False)
        else:
            await interaction.response.send_message("❌ La cola está vacía. No hay nada que mezclar.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="🛑")
    async def detener(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cliente_voz = self.ctx.voice_client
        if cliente_voz:
            id = self.ctx.guild.id
            if id in self.cog.colas:
                while not self.cog.colas[id].empty():
                    self.cog.colas[id].get_nowait()
            await cliente_voz.disconnect(force=True)


class Musica(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.colas = {}
        self.eventos = {}
        self.trabajadores = {}

    def obtener_estado(self, ctx):
        id = ctx.guild.id
        if id not in self.colas or self.trabajadores[id].done():
            self.colas[id] = asyncio.Queue()
            self.eventos[id] = asyncio.Event()
            self.trabajadores[id] = self.bot.loop.create_task(self.motor_reproduccion(ctx))
        return self.colas[id], self.eventos[id]

    async def motor_reproduccion(self, ctx):
        id = ctx.guild.id
        print(f"[LOG] Motor iniciado para {ctx.guild.name}")
        while True:
            try:
                peticion = await asyncio.wait_for(self.colas[id].get(), timeout=60.0)
                print(f"[LOG] Petición recibida: {peticion.get('tipo')}")
            except asyncio.TimeoutError:
                print("[LOG] Inactividad: Desconectando...")
                cliente_voz = ctx.voice_client
                if cliente_voz and cliente_voz.is_connected():
                    await cliente_voz.disconnect(force=True)
                    await ctx.send(embed=discord.Embed(description="💤 **Me he desconectado tras 1 minuto sin reproducir música.**", color=discord.Color.dark_gray()))
                return
            except asyncio.CancelledError:
                return

            cliente_voz = ctx.voice_client
            if not cliente_voz or not cliente_voz.is_connected():
                continue

            loop = self.bot.loop
            tipo_peticion = peticion.get('tipo', 'musica')
            url_audio = ""
            titulo_embed = ""
            url_embed = ""
            duracion = 0
            thumbnail = None
            opciones_uso = opciones_ffmpeg

            # --- PROCESAR TEXTO A VOZ (PREDICADOR CELESTIAL) ---
            if tipo_peticion == 'tts':
                texto = peticion['texto']
                ruta = f"tts_{id}.mp3"
                
                try:
                    communicate = edge_tts.Communicate(texto, "es-ES-AlvaroNeural", rate="-10%", pitch="-15Hz")
                    await communicate.save(ruta)
                    
                    url_audio = ruta
                    titulo_embed = f'🗣️ El Predicador: "{texto}"'
                    opciones_uso = {'options': '-vn -af "equalizer=f=150:t=q:w=1:g=5,aecho=0.8:0.1:200:0.2"'}
                except Exception as e:
                    self.bot.loop.call_soon_threadsafe(self.eventos[id].set)
                    continue

            # --- PROCESAR MÚSICA NORMAL ---
            else:
                try:
                    datos = await loop.run_in_executor(None, lambda: ytdl.extract_info(peticion['busqueda'], download=False))
                    if 'entries' in datos: datos = datos['entries'][0]
                except Exception:
                    continue
                
                if not datos or 'url' not in datos:
                    continue
                    
                url_audio = datos['url']
                titulo_embed = datos.get('title', 'Desconocida')
                url_embed = datos.get('webpage_url', '')
                duracion = datos.get('duration', 0)
                thumbnail = datos.get('thumbnail')

            # --- REPRODUCCIÓN ---
            if cliente_voz.is_playing() or cliente_voz.is_paused():
                cliente_voz.stop()
                await asyncio.sleep(0.3)

            fuente_audio = discord.FFmpegPCMAudio(url_audio, executable="C:/ffmpeg/bin/ffmpeg.exe", **opciones_uso)
            self.eventos[id].clear()

            def al_terminar(error):
                self.bot.loop.call_soon_threadsafe(self.eventos[id].set)

            try:
                cliente_voz.play(fuente_audio, after=al_terminar)
            except discord.errors.ClientException:
                self.bot.loop.call_soon_threadsafe(self.eventos[id].set)
                continue

            minutos, segundos = divmod(duracion, 60)
            
            # --- DISEÑO DEL EMBED ---
            if tipo_peticion == 'tts':
                embed = discord.Embed(title="⛪ Mensaje Celestial", description=f"**{titulo_embed}**", color=discord.Color.gold())
            else:
                embed = discord.Embed(title="🎵 Reproduciendo Ahora", description=f"**[{titulo_embed}]({url_embed})**", color=discord.Color.green())
                embed.add_field(name="Duración", value=f"{minutos}:{segundos:02d}", inline=True)
                if thumbnail: embed.set_thumbnail(url=thumbnail)
            
            embed.add_field(name="Solicitado por", value=peticion['solicitante'], inline=True)
            await ctx.send(embed=embed, view=ControlMusicaView(self, ctx))
            
            await self.eventos[id].wait()

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, busqueda: str):
        if not ctx.message.author.voice:
            await ctx.send(embed=discord.Embed(description="❌ Tienes que estar en un canal de voz primero.", color=discord.Color.red()))
            return
            
        canal_voz_usuario = ctx.message.author.voice.channel
        cliente_voz = ctx.voice_client
        
        # --- BLINDAJE EXTREMO CONTRA TIMEOUTS Y CONEXIONES ZOMBI ---
        try:
            if cliente_voz:
                if cliente_voz.channel != canal_voz_usuario:
                    try:
                        await cliente_voz.move_to(canal_voz_usuario)
                    except Exception:
                        await cliente_voz.disconnect(force=True)
                        cliente_voz = await canal_voz_usuario.connect(timeout=20.0)
                elif not cliente_voz.is_connected():
                    await cliente_voz.disconnect(force=True)
                    cliente_voz = await canal_voz_usuario.connect(timeout=20.0)
            else:
                cliente_voz = await canal_voz_usuario.connect(timeout=20.0)
        except (asyncio.TimeoutError, TimeoutError):
            await ctx.send(embed=discord.Embed(description="❌ **Error de red:** Discord ha tardado demasiado en conectarme al canal de voz. Vuelve a intentarlo.", color=discord.Color.red()))
            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)
            return
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"❌ **Error al conectar:** {e}", color=discord.Color.red()))
            if ctx.voice_client:
                await ctx.voice_client.disconnect(force=True)
            return

        cola, evento = self.obtener_estado(ctx)

        # 1. TEXTO A VOZ (PREDICADOR)
        if busqueda.startswith('"') and busqueda.endswith('"'):
            texto_limpio = busqueda[1:-1]
            await cola.put({'tipo': 'tts', 'texto': texto_limpio, 'solicitante': ctx.message.author.display_name})
            if cliente_voz.is_playing() or cliente_voz.is_paused():
                await ctx.send(embed=discord.Embed(description=f"⛪ **Mensaje añadido a la cola**.\nPosición: **{cola.qsize()}**", color=discord.Color.gold()))
            return

        # 2. SPOTIFY (OEmbed Bypass)
        elif "spotify.com" in busqueda:
            url_oembed = f"https://open.spotify.com/oembed?url={busqueda}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url_oembed) as resp:
                    if resp.status != 200:
                        await ctx.send(embed=discord.Embed(description="❌ Spotify ha bloqueado la lectura de este enlace.", color=discord.Color.red()))
                        return
                    datos_spotify = await resp.json()
            
            titulo = datos_spotify.get('title', 'Desconocido')
            autor = datos_spotify.get('author_name', '')
            
            if "track" in busqueda:
                busqueda_yt = f"ytsearch:{titulo} {autor} audio"
                mensaje_feedback = f"📝 **{titulo} - {autor}** adaptada desde Spotify."
            else:
                busqueda_yt = f"ytsearch:{titulo} playlist"
                mensaje_feedback = f"📝 Playlist **{titulo}** traducida a Mix de YouTube."

            await cola.put({'tipo': 'musica', 'busqueda': busqueda_yt, 'solicitante': ctx.message.author.display_name})
            if cliente_voz.is_playing() or cliente_voz.is_paused():
                await ctx.send(embed=discord.Embed(description=f"{mensaje_feedback}\nPosición: **{cola.qsize()}**", color=discord.Color.brand_green()))

        # 3. YOUTUBE PLAYLISTS
        elif "list=" in busqueda:
            embed_progreso = discord.Embed(title="🔄 Procesando Playlist", description="Cargando...\n`[████████░░░░░░░░░░░░] 50%`", color=discord.Color.gold())
            mensaje = await ctx.send(embed=embed_progreso)
            
            loop = self.bot.loop
            try:
                opts_playlist = {'extract_flat': True, 'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
                datos_playlist = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(opts_playlist).extract_info(busqueda, download=False))
                entries = datos_playlist.get('entries', []) if datos_playlist else []
                entries = [e for e in entries if e]

                if entries:
                    for entrada in entries:
                        url_video = entrada.get('url') or entrada.get('id')
                        if url_video:
                            if not url_video.startswith('http'): url_video = f"https://www.youtube.com/watch?v={url_video}"
                            await cola.put({'tipo': 'musica', 'busqueda': url_video, 'solicitante': ctx.message.author.display_name})
                    await mensaje.edit(embed=discord.Embed(description=f"📚 **{len(entries)}** canciones añadidas a la cola.", color=discord.Color.purple()))
                else:
                    await mensaje.delete()
            except Exception:
                await mensaje.edit(embed=discord.Embed(description="❌ Error procesando mix.", color=discord.Color.red()))
        
        # 4. YOUTUBE NORMAL
        else:
            busqueda_final = busqueda if busqueda.startswith("http") else f"ytsearch:{busqueda}"
            await cola.put({'tipo': 'musica', 'busqueda': busqueda_final, 'solicitante': ctx.message.author.display_name})
            if cliente_voz.is_playing() or cliente_voz.is_paused():
                await ctx.send(embed=discord.Embed(description=f"📝 **{busqueda}** se ha añadido.\nPosición: **{cola.qsize()}**", color=discord.Color.purple()))

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        cliente_voz = ctx.voice_client
        if cliente_voz and cliente_voz.is_playing(): cliente_voz.stop()

    @commands.command(name='pause')
    async def pause(self, ctx):
        cliente_voz = ctx.voice_client
        if cliente_voz and cliente_voz.is_playing(): cliente_voz.pause()

    @commands.command(name='resume')
    async def resume(self, ctx):
        cliente_voz = ctx.voice_client
        if cliente_voz and cliente_voz.is_paused(): cliente_voz.resume()

    @commands.command(name='stop')
    async def stop(self, ctx):
        cliente_voz = ctx.voice_client
        if cliente_voz:
            id = ctx.guild.id
            if id in self.colas:
                while not self.colas[id].empty(): self.colas[id].get_nowait()
            await cliente_voz.disconnect(force=True)

async def setup(bot):
    await bot.add_cog(Musica(bot))