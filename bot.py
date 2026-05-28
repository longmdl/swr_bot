import discord
from discord.ext import commands
import logging

from config import config
from db.connection import init_db
from db.repository import BotRepository
from cogs.announcement import AttendanceView

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")

class RaceDirectorBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents
        )

    async def setup_hook(self):
        logger.info("Setting up database indexes...")
        await init_db()
        
        logger.info("Loading extensions...")
        await self.load_extension("cogs.announcement")
        
        logger.info("Registering persistent views...")
        active_events = await BotRepository.get_all_active_swr_events()
        for event_id in active_events:
            self.add_view(AttendanceView(event_id=event_id))
        
        logger.info("Syncing app commands...")
        await self.tree.sync()

    async def on_ready(self):
        logger.info(f"Bot is live! Logged in as {self.user} (ID: {self.user.id})")

if __name__ == "__main__":
    bot = RaceDirectorBot()
    bot.run(config.DISCORD_TOKEN)