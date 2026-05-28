import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import traceback
import logging

from db.repository import BotRepository

logger = logging.getLogger(__name__)

class AttendanceView(discord.ui.View):
    def __init__(self, event_id: str, links: list = None):
        super().__init__(timeout=None)
        self.event_id = event_id
        
        btn_join = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Tham gia ✅",
            custom_id=f"swr:register:yes:{event_id}",
            row=0
        )
        btn_join.callback = self.join_callback
        self.add_item(btn_join)
        
        btn_absent = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Vắng mặt ❌",
            custom_id=f"swr:register:no:{event_id}",
            row=0
        )
        btn_absent.callback = self.absent_callback
        self.add_item(btn_absent)

        if links:
            # We enforce max 4 buttons since discord limits elements per row or view,
            # but we are just appending URL buttons to row 1.
            for idx, link_dict in enumerate(links):
                btn_link = discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label=f"📁 {link_dict['name']}",
                    url=link_dict['url'],
                    row=1 + (idx // 4) # Shove it to lower rows if too many
                )
                self.add_item(btn_link)

    async def join_callback(self, interaction: discord.Interaction):
        await self._handle_registration(interaction, "attending")

    async def absent_callback(self, interaction: discord.Interaction):
        await self._handle_registration(interaction, "absent")

    async def _handle_registration(self, interaction: discord.Interaction, status: str):
        try:
            event = await BotRepository.get_swr_event(self.event_id)
            if not event:
                await interaction.response.send_message("Sự kiện này không còn tồn tại.", ephemeral=True)
                return

            attending, absent = await BotRepository.update_attendance(self.event_id, interaction.user.id, status)
            
            original_message = interaction.message
            if not original_message or not original_message.embeds:
                await interaction.response.send_message("Lỗi: Không tìm thấy Embed.", ephemeral=True)
                return
            
            embed = original_message.embeds[0]
            
            self._update_roster_fields(embed, attending, absent)
            
            await interaction.response.edit_message(embed=embed)
        except Exception as e:
            logger.error(f"Error in attendance button callback: {e}")
            await interaction.response.send_message("Có lỗi xảy ra khi cập nhật thông tin của bạn.", ephemeral=True)

    def _update_roster_fields(self, embed: discord.Embed, attending_ids: list, absent_ids: list):
        attending_mentions = [f"<@{uid}>" for uid in attending_ids]
        absent_mentions = [f"<@{uid}>" for uid in absent_ids]
        
        attending_text = "\n".join(attending_mentions) if attending_mentions else "Chưa có"
        absent_text = "\n".join(absent_mentions) if absent_mentions else "Chưa có"
        
        attending_name = f"✅ DANH SÁCH THAM GIA ({len(attending_ids)})"
        absent_name = f"❌ VẮNG MẶT ({len(absent_ids)})"
        
        attending_found = False
        absent_found = False
        
        for index, field in enumerate(embed.fields):
            if "DANH SÁCH THAM GIA" in field.name:
                embed.set_field_at(index, name=attending_name, value=attending_text, inline=False)
                attending_found = True
            elif "VẮNG MẶT" in field.name:
                embed.set_field_at(index, name=absent_name, value=absent_text, inline=False)
                absent_found = True
                
        if not attending_found:
            embed.add_field(name=attending_name, value=attending_text, inline=False)
        if not absent_found:
            embed.add_field(name=absent_name, value=absent_text, inline=False)


def create_announcement_embed(event_data: dict) -> discord.Embed:
    title = f"🏎️ SUM WEEKLY RACE - TUẦN {event_data.get('week_number', '?')} ({datetime.now().year})"
    embed = discord.Embed(title=title, color=discord.Color.from_rgb(180, 20, 20))
    
    if event_data.get('timestamp'):
        embed.add_field(
            name="⏰ Thời gian", 
            value=f"<t:{int(event_data['timestamp'])}:F>", 
            inline=False
        )
    
    # Format Race Information
    races_text = f"**Nền tảng:** {event_data['sim_type']}\n\n"
    
    r1 = event_data.get("races", {}).get("1")
    if r1:
        races_text += f"**🏁 Race 1:**\n- Đường đua: {r1['track']}\n- Xe: {r1['car']}\n"
        
    r2 = event_data.get("races", {}).get("2")
    if r2:
        races_text += f"\n**🏁 Race 2:**\n- Đường đua: {r2['track']}\n- Xe: {r2['car']}\n"
        
    embed.add_field(name="🏎️ Thông tin Race", value=races_text, inline=False)
    
    conn_val = (
        f"**Tên Server:** {event_data.get('server_name', 'Saigon United Motorsport - SWR')}\n"
        f"**Password:** {event_data.get('server_password', 'sum123')}"
    )
    embed.add_field(name="⚙️ Kết nối Server", value=conn_val, inline=False)
    
    if event_data.get("poster_url"):
        embed.set_image(url=event_data["poster_url"])
    
    embed.add_field(name="✅ DANH SÁCH THAM GIA (0)", value="Chưa có", inline=False)
    embed.add_field(name="❌ VẮNG MẶT (0)", value="Chưa có", inline=False)
    
    return embed


class InfoModal(discord.ui.Modal, title="General Info"):
    week_num = discord.ui.TextInput(
        label="Week Number",
        placeholder="19",
        max_length=10
    )
    
    date_input = discord.ui.TextInput(
        label="Date (DD/MM/YYYY)",
        placeholder="26/05/2026",
        max_length=15
    )

    time_input = discord.ui.TextInput(
        label="Time (HH:MM)",
        placeholder="20:00",
        max_length=10
    )

    server_name = discord.ui.TextInput(
        label="Server Name",
        default="Saigon United Motorsport - SWR",
        max_length=100
    )

    server_pwd = discord.ui.TextInput(
        label="Server Password",
        default="sum123",
        max_length=50
    )

    def __init__(self, state_dict: dict):
        super().__init__()
        self.state_dict = state_dict
        if state_dict.get("week_number"):
            self.week_num.default = str(state_dict["week_number"])
        if state_dict.get("date_raw"):
            self.date_input.default = str(state_dict["date_raw"])
        if state_dict.get("time_raw_only"):
            self.time_input.default = str(state_dict["time_raw_only"])
        if state_dict.get("server_name"):
            self.server_name.default = str(state_dict["server_name"])
        if state_dict.get("server_password"):
            self.server_pwd.default = str(state_dict["server_password"])

    async def on_submit(self, interaction: discord.Interaction):
        try:
            date_str = self.date_input.value.strip()
            time_str = self.time_input.value.strip()
            dt_str = f"{date_str} {time_str}"
            
            # Parse datetime and enforce ICT (+07:00) timezone
            race_time = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
            ict_tz = timezone(timedelta(hours=7))
            race_time = race_time.replace(tzinfo=ict_tz)
            timestamp = race_time.timestamp()
            
            self.state_dict["week_number"] = self.week_num.value.strip()
            self.state_dict["timestamp"] = timestamp
            self.state_dict["time_raw"] = dt_str
            self.state_dict["date_raw"] = date_str
            self.state_dict["time_raw_only"] = time_str
            self.state_dict["server_name"] = self.server_name.value.strip()
            self.state_dict["server_password"] = self.server_pwd.value.strip()
            
            await interaction.response.send_message("✅ Đã lưu thông tin chung (Info saved).", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Lỗi: Ngày hoặc giờ nhập không đúng định dạng.", ephemeral=True)


class RaceModal(discord.ui.Modal):
    track_name = discord.ui.TextInput(label="Track Name", placeholder="e.g. Nurburgring")
    car_name = discord.ui.TextInput(label="Car Name", placeholder="e.g. GT3")
    track_link = discord.ui.TextInput(label="Track Mod Link (Optional)", required=False)
    car_link = discord.ui.TextInput(label="Car Mod Link (Optional)", required=False)

    def __init__(self, state_dict: dict, race_idx: int):
        super().__init__(title=f"Setup Race {race_idx}")
        self.state_dict = state_dict
        self.race_idx = str(race_idx)
        
        # Load existing if any
        if self.race_idx in state_dict["races"]:
            r = state_dict["races"][self.race_idx]
            self.track_name.default = r.get("track", "")
            self.car_name.default = r.get("car", "")
            self.track_link.default = r.get("track_link", "")
            self.car_link.default = r.get("car_link", "")

    async def on_submit(self, interaction: discord.Interaction):
        self.state_dict["races"][self.race_idx] = {
            "track": self.track_name.value.strip(),
            "car": self.car_name.value.strip(),
            "track_link": self.track_link.value.strip(),
            "car_link": self.car_link.value.strip()
        }
        await interaction.response.send_message(f"✅ Đã lưu cấu hình Race {self.race_idx}.", ephemeral=True)


class ConfirmView(discord.ui.View):
    def __init__(self, event_data: dict, ui_links: list):
        super().__init__()
        self.event_data = event_data
        self.ui_links = ui_links

    @discord.ui.button(label="Xác Nhận & Xuất Bản", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            event_id = await BotRepository.create_swr_event(self.event_data)
            embed = create_announcement_embed(self.event_data)
            
            view = AttendanceView(event_id=event_id, links=self.ui_links)
            await interaction.channel.send(content="@everyone", embed=embed, view=view)
            await interaction.response.edit_message(content="✅ **Thành công! Đã lên lịch Race.**", embed=None, view=None)
        except Exception as e:
             logger.error(f"Error publishing: {e}")
             await interaction.response.edit_message(content=f"❌ **Lỗi lưu DB:** {e}", embed=None, view=None)


class SetupWizardView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, poster_url: str = None):
        super().__init__(timeout=900)
        self.origin_interaction = interaction
        self.event_data = {
            "guild_id": interaction.guild_id,
            "sim_type": "Assetto Corsa",
            "week_number": None,
            "timestamp": None,
            "races": {},
            "server_name": "Saigon United Motorsport - SWR",
            "server_password": "sum123",
            "status": "active",
            "poster_url": poster_url
        }
        
        self.sim_select = discord.ui.Select(
            placeholder="Nền tảng (Assetto Corsa)",
            options=[
                discord.SelectOption(label="Assetto Corsa", value="Assetto Corsa"),
                discord.SelectOption(label="Le Mans Ultimate", value="Le Mans Ultimate")
            ],
            row=0
        )
        self.sim_select.callback = self.on_sim_change
        self.add_item(self.sim_select)

    async def on_sim_change(self, interaction: discord.Interaction):
        self.event_data["sim_type"] = self.sim_select.values[0]
        await interaction.response.send_message(f"Đã cập nhật Nền tảng: {self.event_data['sim_type']}", ephemeral=True)

    @discord.ui.button(label="1. Info & Time", style=discord.ButtonStyle.primary, row=1)
    async def btn_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InfoModal(self.event_data))

    @discord.ui.button(label="2. Setup Race 1", style=discord.ButtonStyle.primary, row=1)
    async def btn_r1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RaceModal(self.event_data, 1))

    @discord.ui.button(label="3. Setup Race 2", style=discord.ButtonStyle.secondary, row=1)
    async def btn_r2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RaceModal(self.event_data, 2))

    @discord.ui.button(label="4. PREVIEW", style=discord.ButtonStyle.success, row=2)
    async def btn_preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.event_data["week_number"] or not self.event_data["timestamp"]:
            await interaction.response.send_message("❌ Thiếu Thời gian hoặc Tuần thi đấu (Vui lòng bấm Bước 1).", ephemeral=True)
            return
        if not self.event_data["races"]:
            await interaction.response.send_message("❌ Phải thiết lập ít nhất Race 1.", ephemeral=True)
            return
            
        embed = create_announcement_embed(self.event_data)
        
        # Build UI Links
        ui_links = []
        for r_idx, r in self.event_data["races"].items():
            if r.get("track_link"):
                ui_links.append({"name": f"Track R{r_idx}", "url": r["track_link"]})
            if r.get("car_link"):
                ui_links.append({"name": f"Car R{r_idx}", "url": r["car_link"]})
                
        view = ConfirmView(self.event_data, ui_links)
        await interaction.response.send_message("[PREVIEW]", embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Delete Race 2", style=discord.ButtonStyle.danger, row=2)
    async def btn_del_r2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if "2" in self.event_data["races"]:
            del self.event_data["races"]["2"]
        await interaction.response.send_message("Đã xóa dữ liệu Race 2.", ephemeral=True)

class AnnouncementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="swr_setup", description="SWR: Setup Race Announcement Wizard")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(poster="Tranh/Poster cho thông báo (tuỳ chọn)")
    async def setup_race(self, interaction: discord.Interaction, poster: discord.Attachment = None):
        poster_url = poster.url if poster else None
        view = SetupWizardView(interaction, poster_url=poster_url)
        await interaction.response.send_message(
            "⚙️ **SWR Race Announcement Wizard**\n"
            "Vui lòng thực hiện theo vòng lặp từ Bước 1 đến Bước 4.", 
            view=view, 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementCog(bot))