import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# Cargar las variables de entorno
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configurar Intents completos y obligatorios para música
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

# Instancia del bot con el prefijo '_'
bot = commands.Bot(command_prefix='_', intents=intents, case_insensitive=True)

@bot.event
async def on_ready():
    print(f'Conectado exitosamente como {bot.user}')
    print('Iniciando sistema de módulos...')
    
    try:
        # Evita duplicados al recargar el cog si se reinicia en caliente
        if 'cogs.musica' in bot.extensions:
            await bot.reload_extension('cogs.musica')
        else:
            await bot.load_extension('cogs.musica')
            
        print('✅ Módulo de música cargado correctamente')
    except Exception as e:
        print(f'❌ Error al cargar música: {e}')
        
    print('¡El bot está listo para recibir comandos!')

if __name__ == '__main__':
    bot.run(TOKEN)