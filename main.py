# ================= IMPORTS =================
import discord
from discord.ext import commands, tasks
import random
import asyncio
import os
from pymongo import MongoClient, ReturnDocument
from flask import Flask
from threading import Thread
import pymongo
from collections import defaultdict
import uuid
import time
from discord.ui import View, Select
import re
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_icon(name, size=(50,50)):
    path = os.path.join(BASE_DIR, "assets", name)
    img = Image.open(path).convert("RGBA")
    return img.resize(size)

# ================= MONGO =================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise Exception("MONGO_URI bulunamadı!")

client = MongoClient(MONGO_URI)

db = client["EwoBotDB"]

collection = db["users"]
economy_col = db["ekonomi"]  
ekonomi_collection = db["ekonomi"]
settings_collection = db["settings"]
settings_col = db["settings"]
oneriban_collection = db["oneriban"]

# fonksyon bakim modu

def bakim_aktif_mi():
    data = settings_collection.find_one({"_id": "bakim_modu"})
    if not data:
        return False
    return data.get("aktif", False)

# ================= FLASK KEEP ALIVE =================
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot aktif!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

active_duels = {}
DUEL_COOLDOWN = 300
TURN_TIMEOUT = 30
MINN_BET = 5000

# ================= BOT =================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.invites = True  # ÖNEMLİ
global_cooldowns = {}
GLOBAL_COOLDOWN = 3


active_duels = {}
duel_history = defaultdict(list)  # anti boost için
DUEL_TIMEOUT = 120  # 2 dakika hamle süresi

def get_prefix(bot, message):

    default_prefixes = ["q!", "Q!", "q", "Q", "ewo ", "Ewo ", "!"]

    if not message.guild:
        return commands.when_mentioned_or(*default_prefixes)(bot, message)

    data = settings_collection.find_one({"_id": f"guild_{message.guild.id}"})

    if data and "prefix" in data:
        return commands.when_mentioned_or(data["prefix"])(bot, message)

    return commands.when_mentioned_or(*default_prefixes)(bot, message)

bot = commands.Bot(
    command_prefix=get_prefix,
    case_insensitive=True,
    intents=intents,
    help_command=None        # 🔥 Default help kapalı
)


@bot.listen("on_command")
async def update_last_active(ctx):
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$set": {"last_active": int(time.time())}}
    )

ISLETMELER = {

    "maden": {"fiyat": 300000, "gelir": 4000},
    "ciftlik": {"fiyat": 450000, "gelir": 7000},
    "otel": {"fiyat": 900000, "gelir": 14000},
    "fabrika": {"fiyat": 2000000, "gelir": 32500},
    "bankasubesi": {"fiyat": 3500000, "gelir": 52500},
    "liman": {"fiyat": 5000000, "gelir": 87500},
    "sirket": {"fiyat": 8000000, "gelir": 148750},
    "holding": {"fiyat": 14000000, "gelir": 225000},

    # YENİ İŞLETMELER
    "teknolojiparki": {"fiyat": 35000000, "gelir": 275000},
    "megafabrika": {"fiyat": 100000000, "gelir": 330000},
    "globalsirket": {"fiyat": 500000000, "gelir": 485000},
    "uzaymadeni": {"fiyat": 2000000000, "gelir": 520000}

}

BOLGELER = {

    "Geceklubu": {"fiyat": 750000, "gelir": 13000},
    "Silahpazari": {"fiyat": 1750000, "gelir": 18000},
    "Kumarhane": {"fiyat": 2500000, "gelir": 28000},
    "Benzinlik": {"fiyat": 3750000, "gelir": 45000},
    "Petrolsahasi": {"fiyat": 5000000, "gelir": 80000},
    "Silahfabrikasi": {"fiyat": 7500000, "gelir": 110000},
    "Yeraltisehri": {"fiyat": 11000000, "gelir": 145000}

}

invite_cache = {}
mafia_col = db["mafias"]
mafia_invites = db["mafia_invites"]
mafia_msg = None
active_drop = False
drop_winner = None
drop_amount = 0
drop_time = 0

# ================= TEST KOMUT =================

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def mongotest(ctx):
    uri = os.getenv("MONGO_URI")
    if uri:
        await ctx.send("✅ MONGO_URI mevcut")
    else:
        await ctx.send("❌ MONGO_URI YOK")

def formatla(sayi):
    return f"{int(sayi):,}".replace(",", ".")

varsayilan_varlikler = {
    "Altın": 50000,
    "Plus": 500000,
    "Bitcoin": 240000,
    "Elmas": 80000,
    "Dolar": 4500,
    "Gümüş": 35000
}

from pymongo import ReturnDocument

def get_user(user_id):
    user_id = str(user_id)

    return collection.find_one_and_update(
        {"_id": user_id},
        {
            "$setOnInsert": {
                "para": 2500,
                "banka": 500,
                "meslek": "İşsiz",
                "xp": 0,
                "level": 1,
                "son_maas": 0,
                "son_gunluk": 0,

                # 📊 İstatistikler
                "cf_sayisi": 0,
                "slot_sayisi": 0,
                "blackjack_sayisi": 0,
                "toplam_kazanc": 0,
                "toplam_kayip": 0,
                "bosanma_sayisi": 0,

                # 🎯 Görev
                "aktif_gorev": None,
                "gorev_progress": 0,
                "tamamlanan_gorev": 0,

                # 🏅 Rozet
                "rozetler": [],
                "aktif_rozet": None,

                # 📦 Envanter
                "envanter": {
                    "Bronz Kasa": 0,
                    "Gümüş Kasa": 0,
                    "Altın Kasa": 0,
                    "Elmas Kasa": 0,
                    "Premium Kasa": 0,
                    "EwoPlus Kasa": 0,
                    "Silah": 0,
                    "Özel Koruma": 0,
                    "Olta": 0,
                    "Yüzük": 0
                },

                # 💎 Yatırımlar
                "yatirimlar": {
                    "Altın": 0,
                    "Plus": 0,
                    "Bitcoin": 0,
                    "Elmas": 0,
                    "Dolar": 0,
                    "Gümüş": 0
                },

                # 🏭 İşletmeler
                "isletmeler": {},

                # ⚔️ PvP Sistemi
                "pvp": {
                    "win": 0,
                    "lose": 0,
                    "rank_point": 0,
                    "duel_count": 0,
                    "afk_penalty_until": 0,
                    "last_duel_users": {}
                },

                # 🏴 MAFYA SİSTEMİ
                "mafia_id": None,        # bulunduğu mafya
                "mafia_role": None,      # leader / member
		"mafia_custom_role": "Mafya Üyesi",
                "mafia_invites": [],     # gelen davetler

                # 💰 Savaş gücü için
                "money_earned": 0,        # bottan kazanılan toplam para

		"premium_until": 0,

		"ewopass": {
	        "level": 1,
 	        "xp": 0,
 	        "claimed_free": [],
  	        "claimed_elite": [],
	        "elite": False
	        },
		
		# 📬 DM ayarları
		"last_active": 0,
		"drop_dm": True
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

def isletme_geliri_hesapla(user, isletme):

    isletmeler = user.get("isletmeler", {})

    if isletme not in isletmeler:
        return 0

    adet = isletmeler[isletme].get("adet", 0)

    saatlik = ISLETMELER.get(isletme, {}).get("gelir", 0)

    return adet * saatlik

async def send_global_drop():

    global active_drop
    global drop_winner

    active_drop = True
    drop_winner = None

    users = collection.find()

    for user in users:
        try:
            member = await bot.fetch_user(int(user["_id"]))

            embed = discord.Embed(
                title="🎁 Kasa Düştü!",
                description="İlk **q!al** yazan **25.000 EwoCoin** kazanacak!",
                color=0xf1c40f
            )

            await member.send(embed=embed)

        except:
            pass

def get_pass_xp_required(level):
    return 100 + (level - 1) * 50

async def ewopass_xp_ekle(user_id, miktar):

    user = get_user(user_id)
    ep = user.get("ewopass", {})

    # ⭐ PREMIUM 2X
    simdi = int(time.time())
    if user.get("premium_until", 0) > simdi:
        miktar *= 2

    level = ep.get("level", 1)
    xp = ep.get("xp", 0)

    xp += miktar

    level_up = False

    while xp >= get_pass_xp_required(level) and level < 30:
        xp -= get_pass_xp_required(level)
        level += 1
        level_up = True

    collection.update_one(
        {"_id": str(user_id)},
        {"$set": {
            "ewopass.level": level,
            "ewopass.xp": xp
        }}
    )

    return level_up

async def xp_ekle(user_id, miktar):

    user = get_user(user_id)

    # ⭐ Premium ise 2x XP
    if is_premium(user):
        miktar *= 2

    xp = int(user.get("xp", 0))
    level = int(user.get("level", 1))

    xp += miktar

    level_up = False

    while xp >= level * 100:
        xp -= level * 100
        level += 1
        level_up = True

    collection.update_one(
        {"_id": str(user_id)},
        {"$set": {"xp": xp, "level": level}}
    )

    # ⭐ Level ödülleri (sadece premium)
    if level_up and is_premium(user):

        if level == 5:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"para": 15000}}
            )

        elif level == 10:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"envanter.Gümüş Kasa": 1}}
            )


        elif level == 15:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"para": 20000}}
            )

        elif level == 20:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"envanter.Altın Kasa": 1}}
            )

        elif level == 20:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"envanter.Altın Kasa": 2}}
            )

        elif level == 50:
            collection.update_one(
                {"_id": str(user_id)},
                {"$inc": {"envanter.Premium Kasa": 1}}
            )

def load_icon(name, size=(50,50)):
    img = Image.open(f"assets/{name}").convert("RGBA")
    return img.resize(size)


def get_reward_text(reward_type):
    if reward_type == "para":
        return "2.000 EwoCoin"
    elif reward_type == "kasa":
        return "1x Kasa"
    elif reward_type == "altin":
        return "1x Altın Kasa"
    elif reward_type == "silah":
        return "1x Silah"
    return ""


# 🔥 OUTLINE TEXT (EN ÖNEMLİ)
def draw_text_outline(draw, pos, text, font, fill, outline=(0,0,0)):
    x, y = pos
    for dx in [-2, -1, 0, 1, 2]:
        for dy in [-2, -1, 0, 1, 2]:
            draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


async def ewopass_resim(user_obj, page=0):

    user = get_user(user_obj.id)

    ep = user.get("ewopass", {
        "level": 1,
        "xp": 0,
        "elite": False,
        "claimed_free": [],
        "claimed_elite": []
    })

    level = ep.get("level", 1)
    xp = ep.get("xp", 0)
    elite = ep.get("elite", False)

    claimed_free = ep.get("claimed_free", [])
    claimed_elite = ep.get("claimed_elite", [])

    width = 1400
    height = 520

    # ================= BACKGROUND =================
    bg = Image.open("assets/background.png").resize((width, height))
    img = bg.convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0,0,0,140))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    # ================= FONT =================
    try:
        font_path = os.path.join(BASE_DIR, "assets", "Poppins-Bold.ttf")
        font_big = ImageFont.truetype(font_path, 80)
        font_mid = ImageFont.truetype(font_path, 40)
        font_small = ImageFont.truetype(font_path, 28)
    except:
        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # ================= ICONS =================
    kasa = load_icon("kasa.png")
    altin = load_icon("altin_kasa.png")
    para = load_icon("para.png")
    silah = load_icon("silah.png")
    kilit = load_icon("kilit.png")
    tik = load_icon("tik.png", (20,20))

    # ================= HEADER =================
    draw_text_outline(draw, (40, 30), "EwoPass", font_big, (255,200,0))
    draw_text_outline(draw, (40, 110), "SEZON 1", font_mid, (255,255,255))

    # ================= XP BAR =================
    max_xp = level * 100
    progress = min(xp / max_xp, 1)

    draw.rectangle((40, 150, 940, 180), fill=(20,20,20))
    draw.rectangle((40, 150, 40 + int(900 * progress), 180), fill=(255,200,0))

    # ================= LEVEL =================
    start = page * 15 + 1
    x_start = 60
    gap = 85

    y_free = 240
    y_elite = 390

    reward_types = [
        "para", "kasa", "silah", "para", "altin",
        "para", "kasa", "silah", "para", "altin",
        "para", "kasa", "silah", "para", "altin"
    ]

    for i in range(15):

        lvl = start + i
        box_x = x_start + i * gap
        rt = reward_types[i]
        text = get_reward_text(rt)

        icon = {
            "para": para,
            "kasa": kasa,
            "altin": altin,
            "silah": silah
        }[rt]

        # ---------- FREE ----------
        outline = (0,200,255) if lvl not in claimed_free else (0,255,120)

        draw.rectangle((box_x, y_free, box_x+70, y_free+70),
                       fill=(40,40,40), outline=outline, width=3)

        img.paste(icon, (box_x+10, y_free+10), icon)

        if lvl in claimed_free:
            img.paste(tik, (box_x+45, y_free+45), tik)

        draw_text_outline(draw, (box_x+15, y_free+75), str(lvl), font_small, (255,255,255))
        draw_text_outline(draw, (box_x-10, y_free+105), text, font_small, (255,255,255))

        # ---------- ELITE ----------
        draw.rectangle((box_x, y_elite, box_x+70, y_elite+70),
                       fill=(80,60,20), outline=(255,200,0), width=3)

        img.paste(icon, (box_x+10, y_elite+10), icon)

        if not elite:
            dark = Image.new("RGBA", (70,70), (0,0,0,160))
            img.paste(dark, (box_x, y_elite), dark)

            small_lock = kilit.resize((25,25))
            img.paste(small_lock, (box_x+22, y_elite+22), small_lock)

        else:
            if lvl in claimed_elite:
                img.paste(tik, (box_x+45, y_elite+45), tik)

        draw_text_outline(draw, (box_x+15, y_elite+75), str(lvl), font_small, (255,255,255))
        draw_text_outline(draw, (box_x-10, y_elite+105), text, font_small, (255,215,0))

    # ================= LABEL =================
    draw_text_outline(draw, (40, y_free-50), "FREE", font_mid, (0,200,255))
    draw_text_outline(draw, (40, y_elite-50), "EWOELITE PASS", font_mid, (255,200,0))

    # ================= FOOTER =================
    status = "AKTİF" if elite else "AKTİF DEĞİL"
    draw_text_outline(draw, (40, 480), f"EwoElite: {status}", font_small, (255,120,120))

    # ================= SAVE =================
    buffer = io.BytesIO()
    img.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)

    return buffer

async def profil_karti_olustur(ctx, user):

    width = 820
    height = 520

    img = Image.new("RGB", (width, height), (47,49,54))

    # ARKAPLAN
    background = user.get("profil_arkaplan")

    if background:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(background) as resp:
                    bg_bytes = await resp.read()

            bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
            bg = bg.resize((width, height))
            img.paste(bg, (0,0))

            overlay = Image.new("RGBA", (width, height), (0,0,0,90))
            img_rgba = img.convert("RGBA")
            img = Image.alpha_composite(img_rgba, overlay).convert("RGB")

        except:
            pass

    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("Poppins-Bold.ttf", 34)
    font_cat = ImageFont.truetype("Poppins-Bold.ttf", 22)
    font_text = ImageFont.truetype("Poppins-Bold.ttf", 18)

    # AVATAR
    avatar_url = ctx.author.display_avatar.url

    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar = avatar.resize((110,110))

    mask = Image.new("L",(110,110),0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0,0,110,110), fill=255)

    img.paste(avatar,(40,40),mask)

    # DATA
    para = user.get("para",0)
    banka = user.get("banka",0)
    faiz = int(banka*0.05)

    meslek = user.get("meslek","Yok")

    if "meslekler" in globals():
        maas = meslekler.get(meslek,{}).get("maas",0)
    else:
        maas = 0

    pvp = user.get("pvp",{}) or {}

    rank_point = pvp.get("rank_point",0)
    win = pvp.get("win",0)
    lose = pvp.get("lose",0)

    try:
        rank_name = get_rank_name(rank_point)
    except:
        rank_name = "Unranked"

    rozet = user.get("aktif_rozet","Yok")

    es_id = user.get("married_to")

    if es_id:
        try:
            es_user = bot.get_user(int(es_id)) or await bot.fetch_user(int(es_id))
            es_name = es_user.name
        except:
            es_name = "Bilinmiyor"
    else:
        es_name = "Yok"

    # MAFYA
    mafia = user.get("mafia", {}) or {}
    mafia_name = mafia.get("name", "Yok")
    mafia_rank = mafia.get("rank", "Yok")

    # TITLE
    draw.text((180,45), f"{ctx.author.name} Hesabı", font=font_title, fill=(255,255,255))

    # EKONOMİ
    y = 170
    draw.text((50,y),"━━ EKONOMİ ━━",font=font_cat,fill=(80,200,255))
    y += 30

    draw.text((60,y),f"Nakit: {formatla(para)}",font=font_text,fill=(255,255,255))
    y += 25

    draw.text((60,y),f"Banka: {formatla(banka)}",font=font_text,fill=(255,255,255))
    y += 25

    draw.text((60,y),f"Faiz: {formatla(faiz)}",font=font_text,fill=(255,255,255))

    # MESLEK
    y = 170
    draw.text((420,y),"━━ MESLEK ━━",font=font_cat,fill=(255,200,120))
    y += 30

    draw.text((430,y),f"Meslek: {meslek}",font=font_text,fill=(255,255,255))
    y += 25

    draw.text((430,y),f"Maaş: {formatla(maas)}",font=font_text,fill=(255,255,255))

    # PVP
    y = 290
    draw.text((50,y),"━━ PVP ━━",font=font_cat,fill=(255,180,120))
    y += 30

    draw.text((60,y),f"Rank: {rank_name}",font=font_text,fill=(255,255,255))
    y += 25

    draw.text((60,y),f"Win: {win}",font=font_text,fill=(255,255,255))

    # EVLİLİK
    y = 260
    draw.text((420,y),"━━ EVLİLİK ━━",font=font_cat,fill=(255,140,200))
    y += 30

    draw.text((430,y),f"Eşi: {es_name}",font=font_text,fill=(255,255,255))

    # ROZET
    y = 370
    draw.text((50,y),"━━ ROZET ━━",font=font_cat,fill=(255,220,120))
    y += 30

    draw.text((60,y),f"{rozet}",font=font_text,fill=(255,255,255))

    # VARLIKLAR
    y = 330
    draw.text((420,y),"━━ VARLIKLAR ━━",font=font_cat,fill=(120,220,255))
    y += 30

    yatirimlar = user.get("yatirimlar",{}) or {}
    text = ""

    for v,a in yatirimlar.items():
        if a > 0:
            text += f"{v}:{a} "

    if not text:
        text = "Yok"

    draw.text((430,y),text,font=font_text,fill=(255,255,255))

    # İŞLETMELER
    y = 440
    draw.text((50,y),"━━ İŞLETMELER ━━",font=font_cat,fill=(120,255,180))
    y += 30

    isletmeler = user.get("isletmeler",{}) or {}
    text2 = ""

    for i,v in isletmeler.items():
        adet = v.get("adet",0)
        if adet > 0:
            text2 += f"{i}:{adet} "

    if not text2:
        text2 = "Yok"

    draw.text((60,y),text2,font=font_text,fill=(255,255,255))

    # MAFYA
    y = 420
    draw.text((420,y),"━━ MAFYA ━━",font=font_cat,fill=(255,80,80))
    y += 30

    draw.text((430,y),f"Grup: {mafia_name}",font=font_text,fill=(255,255,255))
    y += 25

    draw.text((430,y),f"Rütbe: {mafia_rank}",font=font_text,fill=(255,255,255))

    # FOOTER
    draw.text((20,495),"EwoBot Ekonomi Sistemi",font=font_text,fill=(150,150,150))

    buffer = io.BytesIO()
    img.save(buffer,"PNG")
    buffer.seek(0)

    return buffer

class ArkaplanOnayView(discord.ui.View):

    def __init__(self, user_id, url):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.url = url

    @discord.ui.button(label="Onayla", style=discord.ButtonStyle.green)
    async def onayla(self, interaction: discord.Interaction, button: discord.ui.Button):

        collection.update_one(
            {"_id": str(self.user_id)},
            {"$set": {"profil_arkaplan": self.url}}
        )

        user = await bot.fetch_user(self.user_id)

        try:
            await user.send("✅ Profil arka planın **onaylandı**.")
        except:
            pass

        await interaction.response.send_message("Arkaplan onaylandı.", ephemeral=True)
        self.stop()


    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.red)
    async def reddet(self, interaction: discord.Interaction, button: discord.ui.Button):

        collection.update_one(
            {"_id": str(self.user_id)},
            {"$inc": {"banka": ARKAPLAN_FIYAT}}
        )

        user = await bot.fetch_user(self.user_id)

        try:
            await user.send("❌ Profil arka planın **reddedildi**. Para bankana iade edildi.")
        except:
            pass

        await interaction.response.send_message("Arkaplan reddedildi.", ephemeral=True)
        self.stop()

GOREVLER = [

    {"id": "cf_25", "ad": "Kumarbaz I", "tip": "cf", "hedef": 25, "xp": 200},
    {"id": "cf_100", "ad": "Kumarbaz II", "tip": "cf", "hedef": 50, "xp": 500},

    {"id": "slot_50", "ad": "Slot Ustası I", "tip": "slot", "hedef": 25, "xp": 250},
    {"id": "slot_200", "ad": "Slot Ustası II", "tip": "slot", "hedef": 50, "xp": 600},

    {"id": "bj_50", "ad": "Blackjackçi I", "tip": "blackjack", "hedef": 50, "xp": 300},

    {"id": "kazanc_100k", "ad": "100K Kazan", "tip": "kazanc", "hedef": 100000, "xp": 400},
    {"id": "kazanc_1m", "ad": "1M Kazan", "tip": "kazanc", "hedef": 1000000, "xp": 1000},

    {"id": "maas_20", "ad": "Maaş Bağımlısı", "tip": "maas", "hedef": 14, "xp": 300},

    {"id": "gunluk_30", "ad": "Günlük Toplayıcı", "tip": "gunluk", "hedef": 7, "xp": 400},

    {"id": "isletme_10", "ad": "İşletme Patronu I", "tip": "isletme", "hedef": 10, "xp": 500},

]

async def gorev_kontrol(user_id, tip, artis):

    user = get_user(user_id)

    aktif = user.get("aktif_gorev")

    if not aktif:
        return

    if aktif["tip"] != tip:
        return

    yeni = user.get("gorev_progress", 0) + artis

    if yeni >= aktif["hedef"]:

        await xp_ekle(user_id, aktif["xp"])

        collection.update_one(
            {"_id": str(user_id)},
            {
                "$set": {
                    "aktif_gorev": None,
                    "gorev_progress": 0
                },
                "$inc": {
                    "tamamlanan_gorev": 1
                }
            }
        )

    else:
        collection.update_one(
            {"_id": str(user_id)},
            {"$set": {"gorev_progress": yeni}}
        )

ROZETLER = {

    "Kumarbaz I": "25 CF oynayın",
    "Kumarbaz II": "100 CF oynayın",
    "Slotçu I": "50 slot oynayın",
    "Slotçu II": "200 slot oynayın",
    "Blackjackçi": "50 blackjack oynayın",

    "Premium Üye": "Premium üyelik satın al",

    "Zengin I": "100.000 kazan",
    "Zengin II": "1.000.000 kazan",

    "Maaşçı": "20 maaş al",
    "Günlükcü": "30 günlük al",
    "Patron": "10 işletme geliri topla",

    "Level 5": "Level 5 ol",
    "Level 10": "Level 10 ol",
    "Level 20": "Level 20 ol",
    "Level 30": "Level 30 ol",

    "Görevci I": "5 görev tamamla",
    "Görevci II": "20 görev tamamla",

    "Boşanmış": "1 kez boşan",
    "Zengin Banka": "500K banka",
    "Milyoner": "1M nakit",

    "CF 500": "500 CF oynayın",
    "Slot 500": "500 Slot oynayın",
    "BJ 200": "200 Blackjack oynayın",

    "10M Kazanç": "10M toplam kazanç",
    "10M Kayıp": "10M kayıp",

    "Seviye 50": "Level 50 ol",
    "Seviye 75": "Level 75 ol",
    "Seviye 100": "Level 100 ol",

    "Ultra Zengin": "50M servet",
    "Koleksiyoncu": "10 rozet kazan"
}

async def rozet_kontrol(user_id):

    user = get_user(user_id)
    rozetler = user.get("rozetler", [])
    kazanilanlar = []

    if user.get("cf_sayisi", 0) >= 25:
        kazanilanlar.append("Kumarbaz I")

    if user.get("cf_sayisi", 0) >= 100:
        kazanilanlar.append("Kumarbaz II")

    if user.get("slot_sayisi", 0) >= 50:
        kazanilanlar.append("Slotçu I")

    if user.get("slot_sayisi", 0) >= 200:
        kazanilanlar.append("Slotçu II")

    if user.get("blackjack_sayisi", 0) >= 50:
        kazanilanlar.append("Blackjackçi")

    if user.get("toplam_kazanc", 0) >= 100000:
        kazanilanlar.append("Zengin I")

    if user.get("toplam_kazanc", 0) >= 1000000:
        kazanilanlar.append("Zengin II")

    if user.get("level", 0) >= 5:
        kazanilanlar.append("Level 5")

    if user.get("level", 0) >= 10:
        kazanilanlar.append("Level 10")

    if user.get("tamamlanan_gorev", 0) >= 5:
        kazanilanlar.append("Görevci I")

    if user.get("tamamlanan_gorev", 0) >= 20:
        kazanilanlar.append("Görevci II")

    if user.get("bosanma_sayisi", 0) >= 1:
        kazanilanlar.append("Boşanmış")

    if user.get("banka", 0) >= 500000:
        kazanilanlar.append("Zengin Banka")

    if user.get("para", 0) >= 1000000:
        kazanilanlar.append("Milyoner")

    if user.get("toplam_kayip", 0) >= 10000000:
        kazanilanlar.append("10M Kayıp")

    # 🔥 Yeni rozetleri filtrele
    yeni = [r for r in kazanilanlar if r not in rozetler]

    if yeni:
        collection.update_one(
            {"_id": str(user_id)},
            {"$push": {"rozetler": {"$each": yeni}}}
        )

        # 🎉 DM Bildirimi
        user_obj = bot.get_user(int(user_id))
        if user_obj:
            try:
                embed = discord.Embed(
                    title="🎉 Yeni Rozet Kazandın!",
                    description="\n".join([f"🏅 {r}" for r in yeni]),
                    color=discord.Color.gold()
                )
                await user_obj.send(embed=embed)
            except:
                pass

async def kanal_kilitli_mi(guild_id, channel_id):
    data = settings_collection.find_one({"_id": f"guild_{guild_id}"})
    if not data:
        return False

    return channel_id in data.get("disabled_channels", [])

async def global_cooldown_check(ctx):

    user_id = ctx.author.id
    now = time.time()

    last = global_cooldowns.get(user_id, 0)

    if now - last < GLOBAL_COOLDOWN:

        kalan = round(GLOBAL_COOLDOWN - (now - last))

        await ctx.send(
            f"⏳ Komutları çok hızlı kullanıyorsun. **{kalan} saniye** beklemelisin.",
            delete_after=kalan
        )

        return False

    global_cooldowns[user_id] = now
    return True

def global_toplam_para():
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_para": {"$sum": "$para"},
                "total_banka": {"$sum": "$banka"}
            }
        }
    ]

    result = list(collection.aggregate(pipeline))
    if result:
        return result[0]["total_para"] + result[0]["total_banka"]
    return 0 

def oneriban_kontrol(user_id):

    data = oneriban_collection.find_one({"_id": str(user_id)})

    if not data:
        return False

    if data["until"] < int(time.time()):
        oneriban_collection.delete_one({"_id": str(user_id)})
        return False

    return True

def enflasyon_hesapla(taban_fiyat):
    toplam_para = global_toplam_para()

    REFERANS_PARA = 5_000_000  # Global ekonominin dengesi

    oran = toplam_para / REFERANS_PARA

    # Çökme koruması
    oran = max(0.5, min(5, oran))

    yeni_fiyat = int(taban_fiyat * oran)

    return yeni_fiyat


def hesapla_win_chance(user):
    net = user.get("toplam_kazanc", 0) - user.get("toplam_kayip", 0)

    base = 0.50

    # Her 500k net kârda %2 düşür
    modifier = (net / 500_000) * 0.02

    win_chance = base - modifier

    # Limitler
    if win_chance < 0.35:
        win_chance = 0.35
    if win_chance > 0.60:
        win_chance = 0.60

    return win_chance

def is_premium(user):
    return user.get("premium_until", 0) > int(time.time())

def get_rank_name(point):
    if point < 5:
        return "Bronz"
    elif point < 15:
        return "Gümüş"
    elif point < 30:
        return "Altın"
    elif point < 50:
        return "Elmas"
    else:
        return "Efsane"

def enflasyon_orani():
    toplam = global_toplam_para()
    REFERANS = 5_000_000
    oran = toplam / REFERANS
    return max(0.5, min(5, oran))

FREE_REWARDS = {
1: {"para": 2500},
2: {"envanter.Bronz Kasa": 1},
3: {"para": 1000},
4: {"envanter.Olta": 2},
5: {"envanter.Silah": 1},
6: {"para": 3000},
7: {"envanter.Bronz Kasa": 3},
8: {"para": 2000},
9: {"envanter.Altın Kasa": 1},
10: {"yatirimlar.Dolar": 1},
11: {"para": 5000},
12: {"xp": 100},
13: {"envanter.Yüzük": 1},
14: {"para": 4000},
15: {"envanter.Elmas Kasa": 1},

16: {"para": 6000},
17: {"envanter.Gümüş Kasa": 2},
18: {"para": 5000},
19: {"envanter.Olta": 3},
20: {"yatirimlar.Altın": 1},
21: {"para": 8000},
22: {"envanter.Silah": 1},
23: {"xp": 150},
24: {"para": 7000},
25: {"envanter.Altın Kasa": 2},
26: {"para": 9000},
27: {"envanter.Yüzük": 1},
28: {"xp": 200},
29: {"para": 10000},
30: {"envanter.Premium Kasa": 1},
}

ELITE_REWARDS = {
1: {"yatirimlar.Altın": 1},
2: {"para": 5000},
3: {"envanter.Premium Kasa": 1},
4: {"envanter.Olta": 5},
5: {"xp": 300},
6: {"para": 10000},
7: {"envanter.EwoPlus Kasa": 1},
8: {"envanter.Yüzük": 1},
9: {"envanter.Silah": 2},
10: {"yatirimlar.Bitcoin": 1},
11: {"para": 25000},
12: {"envanter.Özel Koruma": 2},
13: {"xp": 500},
14: {"para": 50000},
15: {"envanter.Altın Kasa": 5},

16: {"para": 30000},
17: {"envanter.Elmas Kasa": 2},
18: {"xp": 600},
19: {"yatirimlar.Elmas": 1},
20: {"para": 40000},
21: {"envanter.EwoPlus Kasa": 1},
22: {"xp": 700},
23: {"para": 50000},
24: {"envanter.Altın Kasa": 3},
25: {"xp": 800},
26: {"para": 60000},
27: {"envanter.Özel Koruma": 3},
28: {"xp": 900},
29: {"para": 75000},
31: {"yatirimlar.Plus": 1},
}


def odul_ver(user_id, reward):

    inc_data = {}

    for k, v in reward.items():
        inc_data[k] = v

    collection.update_one(
        {"_id": str(user_id)},
        {"$inc": inc_data}
    )



MARKET_URUNLERI = {
    "Bronz Kasa": {"fiyat": 500},
    "Gümüş Kasa": {"fiyat": 2000},
    "Altın Kasa": {"fiyat": 5000},
    "Elmas Kasa": {"fiyat": 15000},
    "Premium Kasa": {"fiyat": 30000},
    "EwoPlus Kasa": {"fiyat": 60000},
    "Silah": {"fiyat": 15000},
    "Özel Koruma": {"fiyat": 20000},
    "Olta": {"fiyat": 1000}
}

LEVEL_LIMITS = {
    1: 50000,
    2: 60000,
    3: 75000,
    4: 90000,
    5: 100000,
    6: 125000,
    7: 145000,
    8: 165000,
    9: 200000,
    10: 250000,
    12: 275000,
    15: 325000,
    17: 375000,
    20: 450000,
    25: 550000,
    30: 650000,
    35: 700000,
    40: 750000,
    45: 900000,
    50: 1000000,
    60: 1500000,
}

# LEVEL LIMIT HESAPLAMA
def get_level_limit(level):

    limit = 50000

    for lvl, val in sorted(LEVEL_LIMITS.items()):
        if level >= lvl:
            limit = val

    return limit


# KALAN SÜRE
def kalan_sure(saniye):

    saat = saniye // 3600
    saniye %= 3600
    dakika = saniye // 60
    saniye %= 60

    return f"{saat} Saat {dakika} Dakika {saniye} Saniye"

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def param(ctx):
    user_id = str(ctx.author.id)

    user = collection.find_one({"_id": user_id})

    if not user:
        user = {
            "_id": user_id,
            "para": 1000,
            "banka": 0,
            "yatirimlar": {},
            "envanter": {},
            "kullanildi": True
        }
        collection.insert_one(user)
    else:
        collection.update_one(
            {"_id": user_id},
            {"$set": {"kullanildi": True}}
        )

    await ctx.send(
        f"💰 {ctx.author.mention}, Paran: **{formatla(user['para'])} EwoCoin**"
    )
async def claim_rewards(user_id):

    user = get_user(user_id)
    ep = user["ewopass"]

    level = ep["level"]

    free_claimed = ep.get("claimed_free", [])
    elite_claimed = ep.get("claimed_elite", [])

    # FREE
    for lvl in range(1, level+1):
        if lvl not in free_claimed:
            odul_ver(user_id, FREE_REWARDS[lvl])

            collection.update_one(
                {"_id": str(user_id)},
                {"$push": {"ewopass.claimed_free": lvl}}
            )

    # ELITE
    if ep.get("elite"):
        for lvl in range(1, level+1):
            if lvl not in elite_claimed:
                odul_ver(user_id, ELITE_REWARDS[lvl])

                collection.update_one(
                    {"_id": str(user_id)},
                    {"$push": {"ewopass.claimed_elite": lvl}}
                )

class EwoPassView(discord.ui.View):

    def __init__(self, ctx, page=0):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.page = page

    async def update(self, interaction):
        buffer = await ewopass_resim(interaction.user, self.page)

        await interaction.response.edit_message(
            attachments=[discord.File(buffer, "pass.png")],
            view=self
        )

    @discord.ui.button(label="◀️ Geri", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction, button):
        if self.page > 0:
            self.page -= 1
        await self.update(interaction)

    @discord.ui.button(label="🎁 Ödülleri Al", style=discord.ButtonStyle.success, row=0)
    async def claim(self, interaction, button):
        await claim_rewards(interaction.user.id)

        await interaction.response.send_message(
            "🎉 Ödüller alındı!",
            ephemeral=True
        )

        await self.update(interaction)

    @discord.ui.button(label="İleri ▶️", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction, button):
        if self.page < 1:
            self.page += 1
        await self.update(interaction)


@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def ewopass(ctx):

    buffer = await ewopass_resim(ctx.author, 0)
    view = EwoPassView(ctx, 0)

    await ctx.send(
        file=discord.File(buffer, "pass.png"),
        view=view
    )

class EliteConfirmView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=30)
        self.user = user

    @discord.ui.button(label="Satın Al (2.5M)", style=discord.ButtonStyle.green)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Bu sana ait değil.", ephemeral=True)

        user_data = get_user(self.user.id)

        if user_data["para"] < 2500000:
            return await interaction.response.send_message("❌ Yetersiz bakiye!", ephemeral=True)

        collection.update_one(
            {"_id": str(self.user.id)},
            {
                "$inc": {"para": -2500000},
                "$set": {"ewopass.elite": True}
            }
        )

        await interaction.response.edit_message(
            content="💎 EwoElite Pass aktif edildi!",
            view=None
        )

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def elitepass(ctx):

    user = get_user(ctx.author.id)
    ep = user.get("ewopass", {})

    level = ep.get("level", 1)

    embed = discord.Embed(
        title="💎 EwoElite Pass",
        description="Elite pass satın almak istediğine emin misin?",
        color=0xf1c40f
    )

    embed.add_field(name="📊 Seviye", value=f"{level}", inline=True)
    embed.add_field(name="💰 Fiyat", value="2.500.000 EwoCoin", inline=True)

    embed.set_footer(text="Satın alınca tüm elite ödüller açılır")

    await ctx.send(embed=embed, view=EliteConfirmView(ctx.author))

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def elitever(ctx, member: discord.Member):

    if ctx.author.id != 1271933410251772017:
        return

    collection.update_one(
        {"_id": str(member.id)},
        {"$set": {"ewopass.elite": True}}
    )

    await ctx.send("✅ Elite verildi")


@bot.command(name="paragönder")
async def paragonder(ctx, member: discord.Member, miktar: int):

    if member == ctx.author:
        return await ctx.send("❌ Kendine para gönderemezsin")

    if member.bot:
        return await ctx.send("❌ Botlara para gönderemezsin")

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    user = get_user(ctx.author.id)

    if user["para"] < miktar:
        return await ctx.send("❌ Yeterli paran yok")

    now = int(time.time())

    # OWNER limitsiz
    if ctx.author.id != 1271933410251772017:

        level = user.get("level", 1)

        # Level limit
        limit = get_level_limit(level)

        # Premium kontrol
        if user.get("premium_until", 0) > now:
            limit *= 2

        gunluk = user.get("gonderilen_para", 0)
        reset = user.get("gonderilen_reset", now)

        # Günlük reset
        if now >= reset:
            gunluk = 0
            reset = now + 86400

        kalan_limit = limit - gunluk

        if miktar > kalan_limit:

            kalan = reset - now

            embed = discord.Embed(
                title="❌ Transfer Limiti Aşıldı",
                color=discord.Color.red()
            )

            embed.set_thumbnail(url=ctx.author.display_avatar.url)

            embed.add_field(
                name="💸 Günlük Limit",
                value=f"{formatla(limit)} EwoCoin",
                inline=True
            )

            embed.add_field(
                name="📊 Kullanılan",
                value=f"{formatla(gunluk)} EwoCoin",
                inline=True
            )

            embed.add_field(
                name="🟢 Kalan Limit",
                value=f"{formatla(kalan_limit)} EwoCoin",
                inline=False
            )

            embed.add_field(
                name="⏳ Limit Sıfırlanma Süresi",
                value=kalan_sure(kalan),
                inline=False
            )

            embed.set_footer(text="EwoBot Ekonomi Sistemi")

            return await ctx.send(embed=embed)

        # Para gönderme işlemi
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "para": -miktar,
                    "gonderilen_para": miktar
                },
                "$set": {
                    "gonderilen_reset": reset
                }
            }
        )

    else:
        # owner limitsiz gönderir
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": -miktar}}
        )

    # Alıcıya para ekle
    collection.update_one(
        {"_id": str(member.id)},
        {"$inc": {"para": miktar}}
    )

    # Başarılı transfer embed
    embed = discord.Embed(
        title="💸 Para Transferi Başarılı",
        color=discord.Color.green()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    embed.add_field(
        name="👤 Gönderen",
        value=ctx.author.mention,
        inline=True
    )

    embed.add_field(
        name="📥 Alıcı",
        value=member.mention,
        inline=True
    )

    embed.add_field(
        name="💰 Gönderilen Miktar",
        value=f"{formatla(miktar)} EwoCoin",
        inline=False
    )

    embed.set_footer(text="EwoBot Ekonomi Sistemi")

    await ctx.send(embed=embed)

def get_max_bet(user):

    if is_premium(user):
        return 250000

    return 100000

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cf(ctx, miktar: str):

    user = get_user(ctx.author.id)
    MAX_BET = get_max_bet(user)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli bir miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli bir miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send(f"❌ En fazla {formatla(MAX_BET)} oynayabilirsin.")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar}}
    )

    await ctx.send(f"🪙 {formatla(miktar)} ile yazı tura atılıyor...")
    await asyncio.sleep(2)

    win_chance = hesapla_win_chance(user)
    kazandi = random.random() < win_chance

    if kazandi:
        kazanc = miktar * 2

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "para": kazanc,
                    "cf_sayisi": 1,
                    "toplam_kazanc": kazanc
                }
            }
        )

        await ctx.send(f"🎉 Kazandın! +{formatla(kazanc)}")
    else:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "cf_sayisi": 1,
                    "toplam_kayip": miktar
                }
            }
        )

        await ctx.send(f"💀 Kaybettin! -{formatla(miktar)}")

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "cf", 1)
    await rozet_kontrol(ctx.author.id)

@bot.command()
async def kasaatma(ctx):

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$set": {"drop_dm": False}}
    )

    await ctx.send("🔕 Artık kasa DM'leri almayacaksın.")

@bot.command()
async def kasaat(ctx):

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$set": {"drop_dm": True}}
    )

    await ctx.send("📬 Artık kasa DM'leri tekrar alacaksın.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def level(ctx):

    user = get_user(ctx.author.id)

    xp = int(user.get("xp", 0))
    level = int(user.get("level", 1))

    gereken = level * 100

    xp_bar = min(xp, gereken)

    oran = int((xp_bar / gereken) * 10) if gereken > 0 else 0

    bar = "🟩" * oran + "⬜" * (10 - oran)

    embed = discord.Embed(
        title="🏆 Kullanıcı Profili",
        description=f"{ctx.author.mention} kullanıcısının seviyesi",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="📊 Seviye",
        value=f"LVL {level}",
        inline=True
    )

    embed.add_field(
        name="✨ XP",
        value=f"{xp} / {gereken}",
        inline=True
    )

    embed.add_field(
        name="📈 İlerleme",
        value=bar,
        inline=False
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="EwoBot Level Sistemi")

    await ctx.send(embed=embed)

# =====================================================
# 🎰 SLOT KOMUTU (YENİ ORAN SİSTEMİ - FİNAL)
# %20 = 3 aynı (x3)
# %35 = 2 aynı (x2)
# %45 = 1 eşleşme ( %70 kayıp / %30 iade )
# =====================================================

@bot.command()
@commands.cooldown(1, 15, commands.BucketType.user)
async def slot(ctx, miktar: str):

    user = get_user(ctx.author.id)
    MAX_BET = get_max_bet(user)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send(f"❌ En fazla {formatla(MAX_BET)} oynayabilirsin.")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "slot_sayisi": 1}}
    )

    msg = await ctx.send("🎰 Slot dönüyor...")
    await asyncio.sleep(2)

    win_chance = hesapla_win_chance(user)
    kazandi = random.random() < win_chance

    emojis = ["🍒", "🍋", "🍉", "⭐"]

    if kazandi:
        secilen = random.choice(emojis)
        result = [secilen, secilen, secilen]
        kazanc = miktar * 2

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc, "toplam_kazanc": kazanc}}
        )

        text = f"🎉 Kazandın! +{formatla(kazanc)}"
    else:
        result = random.sample(emojis, 3)
        kazanc = 0

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"toplam_kayip": miktar}}
        )

        text = "💀 Kaybettin."

    await msg.edit(content=f"{' | '.join(result)}\n{text}")

    await ewopass_xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "slot", 1)
    await rozet_kontrol(ctx.author.id)

# MAAŞ 
@bot.command(name="maaş")
async def maas(ctx):

    user = get_user(ctx.author.id)
    simdi = time.time()

    if simdi - user.get("son_maas", 0) < 18000:
        kalan = int(18000 - (simdi - user["son_maas"]))
        return await ctx.send(f"⏳ Maaş için {kalan} saniye beklemelisin.")

    meslek = user.get("meslek", "İşsiz")
    maas_miktari = meslekler.get(meslek, {}).get("maas", 0)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": maas_miktari},
            "$set": {"son_maas": simdi}
        }
    )

    await ewopass_xp_ekle(ctx.author.id, 5)
    await ctx.send(f"💰 Maaşını aldın! +{formatla(maas_miktari)} EwoCoin")

@bot.command(name="gunluk")
async def gunluk(ctx):

    user = get_user(ctx.author.id)
    simdi = time.time()

    if simdi - user.get("son_gunluk", 0) < 86400:
        kalan = int(86400 - (simdi - user["son_gunluk"]))
        return await ctx.send(f"⏳ Günlük için {kalan} saniye beklemelisin.")

    level = user.get("level", 1)

    temel = 1000
    bonus = level * 250
    odul = temel + bonus

    # ⭐ Premium bonus
    premium_mesaj = ""
    if is_premium(user):
        odul = int(odul * 1.5)
        premium_mesaj = "\n⭐ Premium bonusu: x1.5"

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": odul},
            "$set": {"son_gunluk": simdi}
        }
    )

    await xp_ekle(ctx.author.id, 10)
    await ewopass_xp_ekle(ctx.author.id, 5)

    await ctx.send(
        f"🎁 Günlük ödülünü aldın!\n"
        f"💰 +{formatla(odul)} EwoCoin"
        f"{premium_mesaj}"
    )




# BANKA SİSTEMİ

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def banka(ctx):
    user = get_user(ctx.author.id)
    faiz = min(int(user["banka"] * 0.05), 500000)

    embed = discord.Embed(
        title="🏦 EwoBank Hesabı",
        color=discord.Color.gold()
    )
    embed.add_field(name="💰 Banka Bakiyesi", value=f"{user['banka']} EwoCoin", inline=False)
    embed.add_field(name="📈 Günlük Faiz", value=f"{faiz} EwoCoin", inline=False)
    embed.set_footer(text="EwoBot Ekonomi Sistemi")

    await ctx.send(embed=embed)

from discord.ext import tasks
import datetime

# BANKA PARA ÇEKME KOMUDU

@bot.command(name="bankayatır")
@commands.cooldown(1, 4, commands.BucketType.user)
async def bankayatır(ctx, miktar: str):

    user = get_user(ctx.author.id)

    # ALL kontrolü
    if miktar.lower() == "all":
        miktar = user["para"]
    else:
        try:
            miktar = int(miktar)
        except:
            return await ctx.send("❌ Geçerli bir miktar yaz")

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    if user["para"] < miktar:
        return await ctx.send("❌ Yeterli nakit paran yok")

    once_nakit = user["para"]
    once_banka = user["banka"]

    sonra_nakit = once_nakit - miktar
    sonra_banka = once_banka + miktar

    # Database güncelle
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "banka": miktar}}
    )

    # Embed
    embed = discord.Embed(
        title=f"🏦 {ctx.author.name} Kullanıcısının Banka Hesabı",
        color=discord.Color.green()
    )

    embed.add_field(
        name="💳 İşlem",
        value="Bankaya Para Yatırma",
        inline=False
    )

    embed.add_field(
        name="💰 İşlem Miktarı",
        value=f"{formatla(miktar)} EwoCoin",
        inline=False
    )

    embed.add_field(
        name="💵 Nakit Para",
        value=f"Önce: {formatla(once_nakit)}\nSonra: {formatla(sonra_nakit)}",
        inline=False
    )

    embed.add_field(
        name="🏦 Banka Hesabı",
        value=f"Önce: {formatla(once_banka)}\nSonra: {formatla(sonra_banka)}",
        inline=False
    )

    embed.set_thumbnail(url=ctx.author.avatar.url)
    embed.set_footer(text="EwoBot Banka Sistemi")

    await ctx.send(embed=embed)



# ================= BANKA ÇEKME =================

@bot.command(name="bankaçek")
@commands.cooldown(1, 4, commands.BucketType.user)
async def bankaçek(ctx, miktar: str):

    user = get_user(ctx.author.id)

    # ALL kontrolü
    if miktar.lower() == "all":
        miktar = user["banka"]
    else:
        try:
            miktar = int(miktar)
        except:
            return await ctx.send("❌ Geçerli bir miktar yaz")

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    if user["banka"] < miktar:
        return await ctx.send("❌ Banka bakiyen yeterli değil")

    once_nakit = user["para"]
    once_banka = user["banka"]

    sonra_nakit = once_nakit + miktar
    sonra_banka = once_banka - miktar

    # Database güncelle
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": miktar, "banka": -miktar}}
    )

    # Embed
    embed = discord.Embed(
        title=f"🏦 {ctx.author.name} Kullanıcısının Banka Hesabı",
        color=discord.Color.red()
    )

    embed.add_field(
        name="💳 İşlem",
        value="Bankadan Para Çekme",
        inline=False
    )

    embed.add_field(
        name="💰 İşlem Miktarı",
        value=f"{formatla(miktar)} EwoCoin",
        inline=False
    )

    embed.add_field(
        name="💵 Nakit Para",
        value=f"Önce: {formatla(once_nakit)}\nSonra: {formatla(sonra_nakit)}",
        inline=False
    )

    embed.add_field(
        name="🏦 Banka Hesabı",
        value=f"Önce: {formatla(once_banka)}\nSonra: {formatla(sonra_banka)}",
        inline=False
    )

    embed.set_thumbnail(url=ctx.author.avatar.url)
    embed.set_footer(text="EwoBot Banka Sistemi")

    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def faiz(ctx):

    user = get_user(ctx.author.id)

    banka = user.get("banka", 0)

    if banka <= 0:
        return await ctx.send("❌ Bankanda para olmadığı için faiz alamazsın.")

    faiz = int(banka * 0.05)

    # Maks faiz limiti
    if faiz > 500000:
        faiz = 500000

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"banka": faiz}}
    )

    await ctx.send(
        f"🏦 {ctx.author.mention}, günlük faizini aldın!\n"
        f"💰 Kazanç: **{formatla(faiz)} EwoCoin**"
    )
from discord.ui import View, Button

class YorumModal(discord.ui.Modal, title="Öneriye Yorum Yap"):

    yorum = discord.ui.TextInput(label="Yorumunuz", style=discord.TextStyle.paragraph)

    def __init__(self, user_id, oneri):
        super().__init__()
        self.user_id = user_id
        self.oneri = oneri

    async def on_submit(self, interaction: discord.Interaction):

        user = await bot.fetch_user(self.user_id)

        embed = discord.Embed(
            title="💬 Önerinize Yorum Yapıldı",
            description=f"Yetkili: {interaction.user.mention}\n\nYorum:\n{self.yorum.value}\n\nÖneriniz:\n{self.oneri}",
            color=discord.Color.blurple()
        )

        await user.send(embed=embed)

        await interaction.response.send_message("Yorum gönderildi.", ephemeral=True)

class OneriView(discord.ui.View):

    def __init__(self, user_id, oneri):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.oneri = oneri

    @discord.ui.button(label="Onayla", style=discord.ButtonStyle.green)
    async def onayla(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = await bot.fetch_user(self.user_id)

        embed = discord.Embed(
            title="✅ Öneriniz Onaylandı",
            description=f"Yetkili: {interaction.user.mention}\n\nÖneriniz:\n{self.oneri}",
            color=discord.Color.green()
        )

        await user.send(embed=embed)

        await interaction.response.send_message("Öneri onaylandı.", ephemeral=True)

    @discord.ui.button(label="Reddet", style=discord.ButtonStyle.red)
    async def reddet(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = await bot.fetch_user(self.user_id)

        embed = discord.Embed(
            title="❌ Öneriniz Reddedildi",
            description=f"Yetkili: {interaction.user.mention}\n\nÖneriniz:\n{self.oneri}",
            color=discord.Color.red()
        )

        await user.send(embed=embed)

        await interaction.response.send_message("Öneri reddedildi.", ephemeral=True)

    @discord.ui.button(label="Yorum Yap", style=discord.ButtonStyle.blurple)
    async def yorum(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(YorumModal(self.user_id, self.oneri))

class HelpMenu(View):



    def __init__(self, author):
        super().__init__(timeout=180)
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message(
                "❌ Bu menüyü sadece komutu kullanan kişi kullanabilir.",
                ephemeral=True
            )
            return False
        return True


class HelpSelect(Select):

    def __init__(self):

        options = [

            discord.SelectOption(label="Ana Menü", emoji="📚"),
            discord.SelectOption(label="Ekonomi", emoji="💰"),
            discord.SelectOption(label="Kumar", emoji="🎲"),
            discord.SelectOption(label="Banka", emoji="🏦"),
            discord.SelectOption(label="Meslek", emoji="💼"),
            discord.SelectOption(label="İşletme", emoji="🏭"),
            discord.SelectOption(label="Mafya", emoji="🕶️"),
            discord.SelectOption(label="Diğer", emoji="📊"),
            discord.SelectOption(label="Moderasyon", emoji="🛠️"),
        ]

        super().__init__(
            placeholder="Kategori seç...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        secim = self.values[0]

        if secim == "Ana Menü":

            embed = discord.Embed(
                title="📚 EwoBot Yardım Menüsü",
                description="""
Aşağıdan bir kategori seçerek komutları görebilirsin.

💰 Ekonomi  
🎲 Kumar  
🏦 Banka  
💼 Meslek  
🏭 İşletme  
🕶️ Mafya  
📊 Diğer  
🛠️ Moderasyon
""",
                color=0x5865F2
            )

        elif secim == "Ekonomi":

            embed = discord.Embed(
                title="💰 Ekonomi Komutları",
                color=0x2ecc71
            )

            embed.add_field(
                name="💳 Hesap",
                value="""
`q!param`
`q!paragönder @kişi miktar`
`q!hesap`
`q!level`
""",
                inline=False
            )

            embed.add_field(
                name="💼 Para Kazanma",
                value="""
`q!dilen`
`q!avlan`
`q!suç`
`q!ara`
`q!balıktut`
`q!çalış`
`q!gunluk`
`q!maaş`
`q!faiz`

""",
                inline=False
            )

            embed.add_field(
                name="📊 Ekonomi",
                value="""
`q!satınal`
`q!sat`
`q!ekonomi`
""",
                inline=False
            )

        elif secim == "Kumar":

            embed = discord.Embed(
                title="🎲 Kumar Komutları",
                color=0xe74c3c
            )

            embed.description = """
`q!cf miktar`
`q!zar miktar`
`q!yuksekdusuk miktar`
`q!slot miktar`
`q!blackjack miktar`
"""

        elif secim == "Banka":

            embed = discord.Embed(
                title="🏦 Banka Komutları",
                color=0xf1c40f
            )

            embed.description = """
`q!banka`
`q!bankayatır miktar`
`q!bankaçek miktar`
"""

        elif secim == "Meslek":

            embed = discord.Embed(
                title="💼 Meslek Komutları",
                color=0x9b59b6
            )

            embed.description = """
`q!meslekler`
`q!meslek al <meslek>`
"""

        elif secim == "İşletme":

            embed = discord.Embed(
                title="🏭 İşletme Komutları",
                color=0x1abc9c
            )

            embed.description = """
`q!işletmeler`
`q!işletmeal <isim> <miktar>`
`q!işletmeyükselt <isim>`
`q!işletmeparaçek`
`q!işletmetop`
`q!sigorta`
"""

        elif secim == "Mafya":

            embed = discord.Embed(
                title="🕶️ Mafya Komutları",
                color=0x2c3e50
            )

            embed.description = """
`q!mafyakur <isim>`
`q!mafyabilgi`
`q!mafyadavet`
`q!mafyakabul`
`q!mafyam`
`q!mafyaayrıl`
`q!mafyayatır`
`q!mafyacek`
`q!gmafyalar`
`q!smafyalar`
`q!mafyadevret`

**Rol Sistemi**
`q!mafyarolleri`
`q!rolisimdegistir <eskirolismi> <yenirolismi>`
`q!mafyaat @kullanıcı`

`q!rololustur`
`q!rolkaldir`
`q!roldegistir`
`q!yöneticiver`
`q!yöneticikaldir`
`q!mafyarol`
`q!mafyalistesi`

**Savaş**
`q!mafyabaskın`
"""

        elif secim == "Diğer":

            embed = discord.Embed(
                title="📊 Diğer Komutlar",
                color=0x3498db
            )

            embed.description = """
`q!gzenginler`
`q!szenginler`
`q!düello`
`q!rank`
`q!kasaatma`
`q!kasaat`
`q!gdüellocular`
`q!sdüellocular`
`q!baskın`
`q!soygun`
`q!enflasyon`
`q!hesaparkaplan <dosya yapıştır>`
`q!kasaaç`
`q!market`
`q!envanter`
`q!evlen`
`q!boşan`
`q!göreval`
`q!görevler`
`q!rozetler`
`q!rozetlerim`
`q!hesaprozetekle`
`q!davet`
`q!premium`
`q!öneriver <mesajınız>`
"""

        elif secim == "Moderasyon":

            embed = discord.Embed(
                title="🛠️ Sunucu Moderasyon",
                color=0xe67e22
            )

            embed.description = """
`q!komutkapat`
`q!komutaç`
`q!prefix <yeni>`
`q!prefixsifirla`
"""

        embed.set_footer(text="EwoBot Yardım Menüsü")

        await interaction.response.edit_message(embed=embed, view=self.view)


@bot.command()
async def yardım(ctx):

    embed = discord.Embed(
        title="📚 EwoBot Yardım Menüsü",
        description="Aşağıdaki menüden kategori seç.",
        color=0x5865F2
    )

    view = HelpMenu(ctx.author)
    view.add_item(HelpSelect())

    await ctx.send(embed=embed, view=view)

# Meslek ve fiyatları
meslekler = {

    "Kripto Milyarderi": {"fiyat": 10_500_000, "maas": 185_000},
    "Dünya Lideri": {"fiyat": 7_500_000, "maas": 110_000},
    "Küresel Finans İmparatoru": {"fiyat": 5_000_000, "maas": 95_000},
    "Holding CEO": {"fiyat": 2_500_000, "maas": 75_000},
    "Cumhurbaşkanı": {"fiyat": 1_000_000, "maas": 50_000},
    "Kartel Lideri": {"fiyat": 900_000, "maas": 47_000},
    "Mafya Babası": {"fiyat": 750_000, "maas": 42_750},
    "Mafya": {"fiyat": 600_000, "maas": 38_450},
    "Siber Güvenlik Uzmanı": {"fiyat": 650_000, "maas": 40_000},
    "Hacker": {"fiyat": 500_000, "maas": 32_250},
    "Yapay Zeka Mühendisi": {"fiyat": 450_000, "maas": 30_000},
    "Yazılım Geliştiricisi": {"fiyat": 80_000, "maas": 18_260},
    "Uzay Pilotu": {"fiyat": 700_000, "maas": 44_000},
    "Pilot": {"fiyat": 300_000, "maas": 28_000},
    "Avukat": {"fiyat": 175_000, "maas": 24_500},
    "Doktor": {"fiyat": 100_000, "maas": 21_350},
    "Mühendis": {"fiyat": 120_000, "maas": 22_000},
    "Polis": {"fiyat": 90_000, "maas": 19_500},
    "Öğretmen": {"fiyat": 70_000, "maas": 16_000},
    "Çöpçü": {"fiyat": 40_000, "maas": 13_250},
    "Garson": {"fiyat": 25_000, "maas": 10_000},
    "Kasiyer": {"fiyat": 15_000, "maas": 8_000},
    "Seyyar Satıcı": {"fiyat": 10_000, "maas": 8_000},
}


class MeslekSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for isim, veri in meslekler.items():
            options.append(
                discord.SelectOption(
                    label=isim,
                    description=f"Fiyat: {formatla(veri['fiyat'])}"
                )
            )

        super().__init__(
            placeholder="Meslek seç...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):

        meslek = self.values[0]
        veri = meslekler[meslek]

        embed = discord.Embed(
            title=f"💼 {meslek}",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="💰 Fiyat",
            value=f"{formatla(veri['fiyat'])} EwoCoin"
        )

        embed.add_field(
            name="💵 Maaş",
            value=f"{formatla(veri['maas'])} EwoCoin"
        )

        embed.set_footer(text="Satın almak için: q!meslek al <meslek>")

        await interaction.response.edit_message(embed=embed, view=self.view)


class MeslekMenu(discord.ui.View):

    def __init__(self, author):
        super().__init__(timeout=120)
        self.author = author
        self.add_item(MeslekSelect())

    async def interaction_check(self, interaction: discord.Interaction):

        if interaction.user != self.author:
            await interaction.response.send_message(
                "❌ Bu menüyü sadece komutu kullanan kişi kullanabilir.",
                ephemeral=True
            )
            return False

        return True


@bot.command(name="meslekler")
async def meslekler_cmd(ctx):

    embed = discord.Embed(
        title="💼 Meslekler",
        description="Aşağıdaki menüden meslek seçebilirsin.",
        color=discord.Color.purple()
    )

    await ctx.send(embed=embed, view=MeslekMenu(ctx.author))

# Meslek satın alma
@bot.command(name="meslek")
@commands.cooldown(1, 4, commands.BucketType.user)
async def meslek_al(ctx, *, secim):

    secim = secim.strip()

    if not secim.lower().startswith("al "):
        return await ctx.send("❌ Kullanım: q!meslek al <Meslek>")

    secim = secim[3:].strip()
    secim = next((m for m in meslekler if m.lower() == secim.lower()), None)

    if not secim:
        return await ctx.send("❌ Böyle bir meslek yok.")

    user = get_user(ctx.author.id)
    fiyat = meslekler[secim]["fiyat"]

    if user["para"] < fiyat:
        return await ctx.send("❌ Paranız yeterli değil.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": -fiyat},
            "$set": {"meslek": secim}
        }
    )

    await ctx.send(f"✅ {ctx.author.mention}, artık {secim} mesleğine sahipsin!")

ARKAPLAN_FIYAT = 100000
LOG_GUILD = 1471843922115301493
LOG_CHANNEL = 1483051326840635442

@bot.command()
async def hesaparkaplan(ctx):

    user = get_user(ctx.author.id)

    if not ctx.message.attachments:
        return await ctx.send("❌ Bir resim dosyası eklemelisin.")

    attachment = ctx.message.attachments[0]

    # sadece resim kabul et
    if not attachment.filename.lower().endswith(("png","jpg","jpeg","webp")):
        return await ctx.send("❌ Sadece **png / jpg / jpeg / webp** formatında resim yükleyebilirsin.")

    url = attachment.url

    simdi = int(time.time())
    premium_until = user.get("premium_until",0)

    premium = premium_until > simdi

    if not premium:

        para = user.get("para",0)

        if para < ARKAPLAN_FIYAT:
            return await ctx.send("❌ Bunun için **100.000 EwoCoin** gerekli.")

        # para kes
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": -ARKAPLAN_FIYAT}}
        )

        mesaj = f"💰 **{formatla(ARKAPLAN_FIYAT)} EwoCoin** kesildi."

    else:
        mesaj = "⭐ Premium kullanıcı olduğun için **ücretsiz** olarak yetkililere gönderildi. Onayb bekleniyor."

    guild = bot.get_guild(LOG_GUILD)
    channel = guild.get_channel(LOG_CHANNEL)

    embed = discord.Embed(
        title="Yeni Hesap Arkaplan İsteği",
        description=f"""
Kullanıcı: {ctx.author}
Sunucu: {ctx.guild.name}
ID: {ctx.author.id}
Premium: {"Evet" if premium else "Hayır"}
""",
        color=0xffcc00
    )

    embed.set_image(url=url)

    view = ArkaplanOnayView(ctx.author.id, url)

    await channel.send(embed=embed, view=view)

    await ctx.send(f"✅ Arkaplan yetkililere gönderildi. Onay bekleniyor.\n{mesaj}")

# =====================================================
# 👤 HESAP KOMUTU (TÜM VARLIKLAR GÖSTERİR)
# =====================================================

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def hesap(ctx):

    user = get_user(ctx.author.id)

    if not user:
        await ctx.send("Botun bu sunucuda yetkileri kısıtlı!.")
        return

    card = await profil_karti_olustur(ctx, user)

    file = discord.File(card, filename="profil.png")

    await ctx.send(file=file)

# Dilenme komutu
@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def dilen(ctx):

    user = get_user(ctx.author.id)
    olay = random.random()

    if olay < 0.30:
        ceza = 200
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": -ceza}}
        )
        await ctx.send("🚨 Zabıta yakaladı! 200 EwoCoin ceza kesildi.")

    elif olay < 0.80:
        kazanc = random.randint(5, 1000)
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc}}
        )
        await ctx.send(f"🙏 Dilenerek {formatla(kazanc)} kazandın.")

    else:
        kazanc = random.randint(1001, 10000)
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc}}
        )
        await ctx.send(f"🕴 Gizemli takım elbiseli adam {formatla(kazanc)} bıraktı!")

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)

# Çalış
@bot.command(name="çalış")
@commands.cooldown(1, 120, commands.BucketType.user)
async def calis(ctx):

    user = get_user(ctx.author.id)

    isler = {
        "Çöpçü": (300, 800),
        "Garson": (500, 1200),
        "Kasiyer": (600, 1500),
        "Taksici": (800, 2000),
        "Madenci": (1200, 3000),
        "Aşçı": (1500, 3500),
        "Öğretmen": (2000, 4500),
        "Polis": (2500, 5000),
        "Mühendis": (3000, 7000),
        "Yazılımcı": (4000, 10000)
    }

    is_sec = random.choice(list(isler.keys()))

    min_para, max_para = isler[is_sec]

    kazanc = random.randint(min_para, max_para)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": kazanc,
                "toplam_kazanc": kazanc
            }
        }
    )

    await ctx.send(
        f"💼 {is_sec} olarak çalıştın ve **{formatla(kazanc)} EwoCoin** kazandın!"
    )

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)
    await rozet_kontrol(ctx.author.id)

# Ara
@bot.command(name="ara")
@commands.cooldown(1, 60, commands.BucketType.user)
async def ara(ctx):

    user = get_user(ctx.author.id)

    yerler = {
        "Çöp Kutusu": (100, 700, 0.40),
        "Araba": (800, 1500, 0.30),
        "Plaj": (1600, 2500, 0.20),
        "Ev": (2600, 7500, 0.10)
    }

    yer = random.choices(
        list(yerler.keys()),
        weights=[v[2] for v in yerler.values()]
    )[0]

    min_p, max_p, _ = yerler[yer]

    # polis riski
    if random.random() < 0.15:
        ceza = 300

        if user["para"] >= ceza:
            collection.update_one(
                {"_id": str(ctx.author.id)},
                {"$inc": {"para": -ceza}}
            )
        else:
            kalan = ceza - user["para"]

            collection.update_one(
                {"_id": str(ctx.author.id)},
                {"$set": {"para": 0}, "$inc": {"banka": -kalan}}
            )

        return await ctx.send("🚓 Polis geldi ve **300 EwoCoin** ceza kesti!")

    kazanc = random.randint(min_p, max_p)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": kazanc}}
    )

    await ctx.send(
        f"🔎 {yer} aradın ve **{formatla(kazanc)} EwoCoin** buldun!"
    )

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)

# Suç
@bot.command(name="suç")
@commands.cooldown(1, 80, commands.BucketType.user)
async def suc(ctx):

    user = get_user(ctx.author.id)

    suc_list = {
        "Evi soymaya çalıştın": (1500, 4000, 300),
        "Market soymaya çalıştın": (2000, 5000, 400),
        "Kuyumcu soymaya çalıştın": (3000, 7000, 700),
        "Bankayı soymaya çalıştın": (5000, 10000, 1000)
    }

    olay = random.choice(list(suc_list.keys()))

    min_p, max_p, ceza = suc_list[olay]

    if random.random() < 0.45:

        if user["para"] >= ceza:
            collection.update_one(
                {"_id": str(ctx.author.id)},
                {"$inc": {"para": -ceza}}
            )
        else:
            kalan = ceza - user["para"]

            collection.update_one(
                {"_id": str(ctx.author.id)},
                {"$set": {"para": 0}, "$inc": {"banka": -kalan}}
            )

        return await ctx.send(f"🚔 {olay} fakat yakalandın! **-{formatla(ceza)} EwoCoin**")

    kazanc = random.randint(min_p, max_p)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": kazanc}}
    )

    await ctx.send(
        f"💰 {olay} ve **{formatla(kazanc)} EwoCoin** kazandın!"
    )

    await xp_ekle(ctx.author.id, 6)
    await ewopass_xp_ekle(ctx.author.id, 5)

# Avlan
@bot.command(name="avlan")
@commands.cooldown(1, 45, commands.BucketType.user)
async def avlan(ctx):

    hayvanlar = {
        "Tavşan": (200, 400),
        "Ördek": (300, 600),
        "Tilki": (500, 900),
        "Geyik": (900, 1500),
        "Yaban Domuzu": (1200, 2000),
        "Kurt": (1800, 2600),
        "Ayı": (2500, 3500),
        "Dağ Keçisi": (3000, 4200),
        "Kartal": (3500, 4800),
        "Altın Geyik": (4500, 5000)
    }

    hayvan = random.choice(list(hayvanlar.keys()))

    min_p, max_p = hayvanlar[hayvan]

    kazanc = random.randint(min_p, max_p)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": kazanc}}
    )

    await ctx.send(
        f"🏹 {hayvan} avladın ve **{formatla(kazanc)} EwoCoin** kazandın!"
    )

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)

@bot.command(name="al")
@commands.cooldown(1, 5, commands.BucketType.user)
async def al(ctx):

    global active_drop
    global drop_winner
    global drop_amount
    global drop_time

    if not active_drop:

        if drop_winner:
            return await ctx.send(
                f"❌ {drop_winner.mention} çoktan kasayı kaptı!"
            )

        return

    now = int(time.time())

    # kasa henüz açılmadıysa
    if now < drop_time:

        kalan = drop_time - now

        dakika = kalan // 60
        saniye = kalan % 60

        if dakika > 0:
            return await ctx.send(
                f"⏳ Kasa henüz açılmadı!\n"
                f"📦 Açılmasına **{dakika} dakika {saniye} saniye** var."
            )
        else:
            return await ctx.send(
                f"⏳ Kasa henüz açılmadı!\n"
                f"📦 Açılmasına **{saniye} saniye** var."
            )

    # kasa alındıysa
    if drop_winner:
        return await ctx.send(
            f"❌ {drop_winner.mention} çoktan kasayı kaptı!"
        )

    # kazanan
    active_drop = False
    drop_winner = ctx.author

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": drop_amount}},
        upsert=True
    )

    await ctx.send(
        f"🎉 {ctx.author.mention} kasayı kaptı! **{formatla(drop_amount)} EwoCoin** kazandı!"
    )

# drop
@bot.command()
async def drop(ctx, miktar: int, zaman: str):

    global active_drop
    global drop_winner
    global drop_amount
    global drop_time

    if ctx.author.id != 1271933410251772017:
        return

    dakika = int(zaman.replace("m", ""))
    acilis = int(time.time()) + dakika * 60

    # Drop bilgilerini ayarla
    active_drop = True
    drop_winner = None
    drop_amount = miktar
    drop_time = acilis

    # Sadece gerekli verileri çek
    users = list(collection.find({}, {"_id": 1, "drop_dm": 1, "last_active": 1}))

    await ctx.send(f"📦 Drop başlatıldı. {len(users)} kullanıcı kontrol ediliyor...")

    basarili = 0
    basarisiz = 0

    for user in users:

        if "_id" not in user:
            continue

        # 🔕 DM kapatmış mı
        if not user.get("drop_dm", True):
            continue

        # ⏳ 10 gün aktif değilse
        if int(time.time()) - user.get("last_active", 0) > 864000:
            continue

        try:

            user_id = int(user["_id"])

            member = bot.get_user(user_id)

            if not member:
                member = await bot.fetch_user(user_id)

            if not member:
                continue

            embed = discord.Embed(
                title="🎁 Ewo Kasası Geldi!",
                description=(
                    f"Bir kasa düştü!\n\n"
                    f"💰 Ödül: **{formatla(miktar)} EwoCoin**\n"
                    f"⏳ Açılma: **{dakika} dakika sonra**\n\n"
                    f"Açılınca **q!al** yazan kazanacak!"
                ),
                color=0xf1c40f
            )

            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(
                text="🔕 Kasa DM almak istemiyorsan butona bas. Tekrar açmak için: q!kasaat"
            )

            view = discord.ui.View(timeout=None)

            button = discord.ui.Button(
                label="Kasa DM kapat",
                style=discord.ButtonStyle.red
            )

            async def button_callback(interaction):

                collection.update_one(
                    {"_id": str(interaction.user.id)},
                    {"$set": {"drop_dm": False}}
                )

                await interaction.response.send_message(
                    "🔕 Artık kasa DM'leri almayacaksın.",
                    ephemeral=True
                )

            button.callback = button_callback
            view.add_item(button)

            try:
                await member.send(embed=embed, view=view)
                basarili += 1

            except discord.HTTPException as e:

                basarisiz += 1

                if e.status == 429:
                    retry = getattr(e, "retry_after", 10)
                    await asyncio.sleep(retry)

            await asyncio.sleep(3.5)

        except:
            basarisiz += 1

    await ctx.send(
        f"📦 Drop DM gönderimi tamamlandı!\n\n"
        f"📨 Gönderilen: **{basarili}**\n"
        f"❌ Başarısız: **{basarisiz}**"
    )
class BolgeSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for isim, veri in BOLGELER.items():

            options.append(
                discord.SelectOption(
                    label=isim.capitalize(),
                    description=f"Fiyat: {formatla(veri['fiyat'])} | Saatlik: {formatla(veri['gelir'])}"
                )
            )

        super().__init__(
            placeholder="Bölge seç...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        secilen = self.values[0].lower()
        veri = BOLGELER[secilen]

        embed = discord.Embed(
            title=f"🌍 {secilen.capitalize()}",
            color=0x2f3136
        )

        embed.add_field(
            name="💰 Fiyat",
            value=f"{formatla(veri['fiyat'])} Ewocoin",
            inline=False
        )

        embed.add_field(
            name="📈 Saatlik Gelir",
            value=f"{formatla(veri['gelir'])} Ewocoin",
            inline=False
        )

        embed.set_footer(text="Satın almak için: qbölgeal <isim>")

        await interaction.response.edit_message(embed=embed, view=self.view)

class BolgeMenu(discord.ui.View):

    def __init__(self, author):
        super().__init__(timeout=120)
        self.author = author
        self.add_item(BolgeSelect())

    async def interaction_check(self, interaction):

        if interaction.user != self.author:
            await interaction.response.send_message(
                "❌ Bu menüyü sadece komutu kullanan kişi kullanabilir.",
                ephemeral=True
            )
            return False

        return True

@bot.command()
async def dmduyuru(ctx, *, mesaj):

    if ctx.author.id != 1271933410251772017:
        return await ctx.send("❌ Bu komutu kullanamazsın.")

    users = list(collection.find({}, {"_id": 1}))

    await ctx.send(f"📢 Duyuru gönderiliyor... ({len(users)} kullanıcı)")

    basarili = 0
    basarisiz = 0

    for user in users:

        if "_id" not in user:
            continue

        try:

            user_id = int(user["_id"])

            member = bot.get_user(user_id)

            if not member:
                member = await bot.fetch_user(user_id)

            if not member:
                continue

            embed = discord.Embed(
                title="📢 EwoBot Duyuru",
                description=mesaj,
                color=discord.Color.blurple()
            )

            embed.set_thumbnail(url=bot.user.display_avatar.url)
            embed.set_footer(text="EwoBot")

            await member.send(embed=embed)

            basarili += 1

            await asyncio.sleep(5)

        except:
            basarisiz += 1

    await ctx.send(
        f"✅ Duyuru tamamlandı!\n"
        f"📨 Gönderilen: **{basarili}**\n"
        f"❌ Başarısız: **{basarisiz}**"
    )

# BLACK JACKK

@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def blackjack(ctx, miktar: str = None):

    if miktar is None:
        return await ctx.send("❌ Kullanım: q!blackjack <miktar / all>")

    MAX_BET = 100000
    user = get_user(ctx.author.id)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli bir miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli bir miktar gir.")

    if miktar > MAX_BET:
        miktar = MAX_BET

    if user["para"] < miktar:
        return await ctx.send("❌ Yeterli paran yok.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "blackjack_sayisi": 1}}
    )

    msg = await ctx.send("🃏 Kartlar Dağıtılıyor...")
    await asyncio.sleep(2)

    kartlar = [2,3,4,5,6,7,8,9,10,10,10,10,11]

    oyuncu = [random.choice(kartlar), random.choice(kartlar)]
    bot_kart = [random.choice(kartlar), random.choice(kartlar)]

    def toplam(el):
        t = sum(el)
        while t > 21 and 11 in el:
            el[el.index(11)] = 1
            t = sum(el)
        return t

    oyuncu_toplam = toplam(oyuncu)
    bot_toplam = toplam(bot_kart)

    win_chance = hesapla_win_chance(user)

    bot_limit = 17
    if win_chance <= 0.40:
        bot_limit = 18

    while bot_toplam < bot_limit:
        bot_kart.append(random.choice(kartlar))
        bot_toplam = toplam(bot_kart)

    if oyuncu_toplam > 21:
        sonuc = "💀 Battın! Kaybettin."
        collection.update_one({"_id": str(ctx.author.id)}, {"$inc": {"toplam_kayip": miktar}})

    elif bot_toplam > 21 or oyuncu_toplam > bot_toplam:
        kazanc = miktar * 2
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc, "toplam_kazanc": kazanc}}
        )
        sonuc = f"🎉 Kazandın! +{formatla(kazanc)}"

    elif oyuncu_toplam == bot_toplam:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": miktar}}
        )
        sonuc = "🤝 Berabere! Paran iade edildi."

    else:
        sonuc = "💀 Kaybettin."
        collection.update_one({"_id": str(ctx.author.id)}, {"$inc": {"toplam_kayip": miktar}})

    mesaj = (
        "🃏 **Blackjack**\n\n"
        f"👤 Sen: {oyuncu} → {oyuncu_toplam}\n"
        f"🤖 Bot: {bot_kart} → {bot_toplam}\n\n"
        f"{sonuc}"
    )

    await msg.edit(content=mesaj)

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "blackjack", 1)
    await rozet_kontrol(ctx.author.id)

# ZAR KOMUTU
@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def zar(ctx, miktar: str):

    user = get_user(ctx.author.id)
    MAX_BET = get_max_bet(user)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send(f"❌ En fazla {formatla(MAX_BET)} oynayabilirsin.")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "zar_sayisi": 1}}
    )

    await ctx.send("🎲 Zar atılıyor...")
    await asyncio.sleep(2)

    win_chance = hesapla_win_chance(user)
    kazandi = random.random() < win_chance

    if kazandi:
        zar_sonuc = random.choice([4, 5, 6])
        kazanc = miktar * 2

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc, "toplam_kazanc": kazanc}}
        )

        mesaj = f"🎲 Zar: {zar_sonuc}\n🎉 Kazandın! +{formatla(kazanc)}"
    else:
        zar_sonuc = random.choice([1, 2, 3])

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"toplam_kayip": miktar}}
        )

        mesaj = f"🎲 Zar: {zar_sonuc}\n💀 Kaybettin."

    await ctx.send(mesaj)

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "zar", 1)
    await rozet_kontrol(ctx.author.id)

# yuksek asagı
@bot.command()
@commands.cooldown(1, 8, commands.BucketType.user)
async def yuksekdusuk(ctx, miktar: str, secim: str):

    user = get_user(ctx.author.id)
    MAX_BET = get_max_bet(user)

    secim = secim.lower()

    if secim not in ["yuksek", "dusuk"]:
        return await ctx.send("❌ Seçim: yuksek / dusuk")

    # miktar kontrol
    if miktar.lower() == "all":
        miktar = min(user.get("para", 0), MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send("❌ Maksimum 100.000 oynayabilirsin.")

    if user.get("para", 0) < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    # bahis düş
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "yuksekdusuk_sayisi": 1}}
    )

    await ctx.send("🎯 Sayı belirleniyor...")
    await asyncio.sleep(2)

    sayi = random.randint(1, 100)

    # gerçek oyun mantığı
    if secim == "yuksek":
        kazandi = sayi > 50
    else:
        kazandi = sayi <= 50

    if kazandi:

        kazanc = miktar * 2

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "para": kazanc,
                    "toplam_kazanc": kazanc
                }
            }
        )

        sonuc = (
            f"🎯 Sayı: **{sayi}**\n"
            f"🎉 Kazandın!\n"
            f"💰 +{formatla(kazanc)}"
        )

    else:

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "toplam_kayip": miktar
                }
            }
        )

        sonuc = (
            f"🎯 Sayı: **{sayi}**\n"
            f"💀 Kaybettin!\n"
            f"💸 -{formatla(miktar)}"
        )

    await ctx.send(sonuc)

    # xp ve görev
    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "yuksekdusuk", 1)
    await rozet_kontrol(ctx.author.id)

# ================== EKONOMİ KOMUTU ==================

@bot.command(name="ekonomi")
@commands.cooldown(1, 5, commands.BucketType.user)
async def ekonomi(ctx):

    embed = discord.Embed(
        title="📊 EwoBot Global Ekonomi",
        description="Güncel yatırım varlık fiyatları aşağıdadır.\nAlmak için: `q!satınal varlık miktar`\nSatmak için: `q!sat varlık miktar`",
        color=discord.Color.dark_blue()
    )

    for varlik, varsayilan_fiyat in varsayilan_varlikler.items():

        veri = economy_col.find_one({"_id": varlik})

        if not veri:
            fiyat = varsayilan_fiyat
            economy_col.update_one(
                {"_id": varlik},
                {"$set": {"current_price": varsayilan_fiyat}},
                upsert=True
            )
        else:
            fiyat = veri.get("current_price", varsayilan_fiyat)

        embed.add_field(
            name=f"💎 {varlik}",
            value=f"Fiyat: {formatla(fiyat)}",
            inline=False
        )

    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="EwoBot Ekonomi Sistemi")

    await ctx.send(embed=embed)

# ================== SATINAL KOMUTU ==================

# =====================================================
# 💰 SATINAL KOMUTU (TÜM VARLIKLAR ÇALIŞIR)
# =====================================================

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def satınal(ctx, varlik_adi: str, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Miktar 1 veya daha büyük olmalı.")

    user = get_user(ctx.author.id)

    # Varsayılan fiyatlar
    varsayilan_varlikler = {
        "Altın": 50000,
        "Plus": 500000,
        "Bitcoin": 240000,
        "Elmas": 80000,
        "Dolar": 4500,
        "Gümüş": 35000
    }

    # Kullanıcı input düzeltme
    varlik_input = varlik_adi.lower()

    varlik_map = {
        "altın": "Altın",
        "altin": "Altın",
        "plus": "Plus",
        "ewoplus": "Plus",
        "bitcoin": "Bitcoin",
        "elmas": "Elmas",
        "dolar": "Dolar",
        "gümüş": "Gümüş",
        "gumus": "Gümüş"
    }

    if varlik_input not in varlik_map:
        return await ctx.send("❌ Böyle bir varlık yok.")

    varlik = varlik_map[varlik_input]

    # Güncel fiyatı database'den çek
    veri = economy_col.find_one({"_id": varlik})

    if veri:
        fiyat = veri.get("current_price", varsayilan_varlikler[varlik])
    else:
        fiyat = varsayilan_varlikler[varlik]
        economy_col.update_one(
            {"_id": varlik},
            {"$set": {"current_price": fiyat}},
            upsert=True
        )

    toplam = fiyat * miktar

    if user["para"] < toplam:
        return await ctx.send("❌ Paran yetmiyor.")

    # Parayı düş
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -toplam}}
    )

    # Yatırımı ekle
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {f"yatirimlar.{varlik}": miktar}}
    )

    await ctx.send(
        f"✅ {miktar} adet {varlik} satın alındı.\n"
        f"💰 Birim fiyat: {fiyat:,}\n"
        f"💸 Toplam: {toplam:,}"
    )

# öneri
@bot.command()
async def öneriban(ctx, user: discord.User, süre: str):

    # Sadece belirli kullanıcı kullanabilir
    if ctx.author.id != 1271933410251772017:
        return await ctx.send("Bu komutu kullanma yetkin yok.")

    # Süreyi kontrol et (örn: 1m, 10d, 300d, 2h gibi)
    match = re.match(r"(\d+)([smhd])", süre)

    if not match:
        return await ctx.send("Geçersiz süre formatı. Örnek: 1m, 10d, 2h")

    miktar = int(match.group(1))
    birim = match.group(2)

    saniye_carpan = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    until = int(time.time()) + (miktar * saniye_carpan[birim])

    oneriban_collection.update_one(
        {"_id": str(user.id)},
        {"$set": {"until": until}},
        upsert=True
    )

    await ctx.send(f"{user.mention} öneri sisteminden {süre} yasaklandı.")

@bot.command()
@commands.cooldown(1, 600, commands.BucketType.user)
async def öneriver(ctx, *, oneri):

    if oneriban_kontrol(ctx.author.id):
        return await ctx.send("❌ Öneri verme yetkin geçici olarak yasaklandı.")

    log_channel = bot.get_channel(1482875494687969402)

    embed = discord.Embed(
        title="📩 EwoBot Öneri Sistemi",
        color=discord.Color.gold()
    )

    embed.add_field(name="Öneriyi Yapan", value=ctx.author.mention, inline=False)
    embed.add_field(name="Zaman", value=f"<t:{int(time.time())}:F>", inline=False)
    embed.add_field(name="Öneri Yapılan Sunucu", value=ctx.guild.name, inline=False)
    embed.add_field(name="Öneri", value=oneri, inline=False)

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    view = OneriView(ctx.author.id, oneri)

    await log_channel.send(embed=embed, view=view)

    # kullanıcıya dm

    dm_embed = discord.Embed(
        title="📬 EwoBot Öneri Sistemi",
        description="Öneriniz için teşekkürler.\nÖneriniz logs kanalına gönderildi.\nOnaylandığında veya reddedildiğinde size bildirilecektir.",
        color=discord.Color.green()
    )

    dm_embed.add_field(name="Öneriniz", value=oneri, inline=False)
    dm_embed.set_thumbnail(url=bot.user.display_avatar.url)

    try:
        await ctx.author.send(embed=dm_embed)
    except:
        pass

    await ctx.send("✅ Öneriniz alındı.")



# ================== SAT KOMUTU ==================

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def sat(ctx, varlik_adi: str, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Miktar 1 veya daha büyük olmalı.")

    user = get_user(ctx.author.id)

    varlik_adi = varlik_adi.lower()

    varlik_map = {
        "altın": "Altın",
        "altin": "Altın",
        "bitcoin": "Bitcoin",
        "plus": "Plus",
        "plus": "Plus",
        "elmas": "Elmas",
        "dolar": "Dolar",
        "gümüş": "Gümüş",
        "gumus": "Gümüş"
    }

    if varlik_adi not in varlik_map:
        return await ctx.send("❌ Geçersiz varlık adı.")

    varlik = varlik_map[varlik_adi]

    sahip = user.get("yatirimlar", {}).get(varlik, 0)

    if sahip < miktar:
        return await ctx.send("❌ Bu kadar varlığın yok.")

    # DATABASE'DEN GÜNCEL FİYAT
    veri = economy_col.find_one({"_id": varlik})
    fiyat = veri["current_price"]

    toplam = fiyat * miktar

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": toplam,
                f"yatirimlar.{varlik}": -miktar
            }
        }
    )

    await ctx.send(
        f"✅ {miktar} {varlik} satıldı!\n"
        f"💰 Kazanç: {formatla(toplam)}"
    )

# ------------------- Cooldown hata mesajı --------------------
import math

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandOnCooldown):

        kalan = math.ceil(error.retry_after)

        await ctx.send(
            f"⏳ Bu komutu tekrar kullanmak için **{kalan} saniye** beklemelisin!",
            delete_after=kalan
        )
# ------------------ Bot Durum ---------------------
from discord.ext import tasks

@tasks.loop(seconds=30)
async def durum_degistir():
    # Sunucu sayısı
    sunucu_sayisi = len(bot.guilds)

    # Tüm sunuculardaki benzersiz kullanıcı sayısı
    tum_uyeler = set()
    for guild in bot.guilds:
        for uye in guild.members:
            tum_uyeler.add(uye.id)

    oyuncu_sayisi = len(tum_uyeler)

    # 2 farklı durum
    if durum_degistir.counter % 2 == 0:
        await bot.change_presence(activity=discord.Game(name="q!yardım | q!öneriver | prefix: q!"))
    else:
        await bot.change_presence(activity=discord.Game(name=f"{sunucu_sayisi} Sunucu | {oyuncu_sayisi} Oyuncu"))

    durum_degistir.counter += 1

# Sayaç başlat
durum_degistir.counter = 0
# ------ BOT EKLEME İCİN -----------
@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def davet(ctx):

    invite_link = "https://discord.com/oauth2/authorize?client_id=1475533273160618204&permissions=8&scope=bot%20applications.commands"

    view = discord.ui.View()

    invite_button = discord.ui.Button(
        label="🤖 Botu Sunucuna Ekle",
        url=invite_link
    )

    view.add_item(invite_button)

    await ctx.send(
        "Botu sunucuna eklemek için aşağıdaki butona tıkla:",
        view=view
    )

# Help kapatma 
@bot.command()
async def help(ctx):
    await ctx.send("❌ Yanlış Komut! Lütfen `q!yardım` yazınız.")

# =====================================================
# 🌍 GLOBAL EwoPlusCoin ZENGİNLER
# =====================================================

@bot.command()
@commands.cooldown(1, 30, commands.BucketType.user)
async def gzenginler(ctx):

    tum_kullanicilar = collection.find()
    liste = []

    for user in tum_kullanicilar:
        para = user.get("para", 0)
        banka = user.get("banka", 0)
        toplam_servet = para + banka

        if toplam_servet > 0:
            liste.append((user["_id"], toplam_servet))

    sirali = sorted(liste, key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🌍 Global En Zenginler Listesi",
        color=discord.Color.gold()
    )

    if not sirali:
        embed.description = "Henüz veri yok."
        return await ctx.send(embed=embed)

    for i, (user_id, servet) in enumerate(sirali, 1):
        try:
            uye = await bot.fetch_user(int(user_id))
            user_data = get_user(user_id)

            premium_tag = "⭐ " if is_premium(user_data) else ""
            crown = "👑 " if i == 1 else ""

            embed.add_field(
                name=f"{crown}{i}. {premium_tag}{uye.name}",
                value=f"💰 Serveti = {formatla(servet)} EwoCoin",
                inline=False
            )
        except:
            continue

    await ctx.send(embed=embed)

# =====================================================
# 🔁 10 DAKİKADA BİR GLOBAL EwoPlusCoin
# =====================================================

GLOBAL_ZENGINLER_KANAL_ID = 1479627190864838778
global_zenginler_mesaj_id = None


GLOBAL_ZENGINLER_KANAL_ID = 1479627190864838778
global_zenginler_mesaj_id = None


@tasks.loop(hours=1)
async def otomatik_gzenginler():
    global global_zenginler_mesaj_id

    try:
        kanal = bot.get_channel(GLOBAL_ZENGINLER_KANAL_ID)
        if not kanal:
            print("Global zenginler kanalı bulunamadı.")
            return

        tum_kullanicilar = collection.find()
        liste = []

        for user in tum_kullanicilar:
            para = user.get("para", 0)
            banka = user.get("banka", 0)
            toplam_servet = para + banka

            if toplam_servet > 0:
                liste.append((user["_id"], toplam_servet))

        sirali = sorted(liste, key=lambda x: x[1], reverse=True)[:10]

        embed = discord.Embed(
            title="🌍 Global En Zenginler",
            color=discord.Color.gold()
        )

        if not sirali:
            embed.description = "Henüz veri yok."
        else:
            for i, (user_id, servet) in enumerate(sirali, 1):

                uye = bot.get_user(int(user_id))
                if not uye:
                    continue

                user_data = get_user(user_id)

                premium_tag = "⭐ " if is_premium(user_data) else ""
                crown = "👑 " if i == 1 else ""

                embed.add_field(
                    name=f"{crown}{i}. {premium_tag}{uye.name}",
                    value=f"💰 {formatla(servet)} EwoCoin",
                    inline=False
                )

        if global_zenginler_mesaj_id:
            try:
                mesaj = await kanal.fetch_message(global_zenginler_mesaj_id)
                await mesaj.edit(embed=embed)
                return
            except:
                global_zenginler_mesaj_id = None

        mesaj = await kanal.send(embed=embed)
        global_zenginler_mesaj_id = mesaj.id

    except Exception as e:
        print("Global zenginler hata:", e)


@otomatik_gzenginler.before_loop
async def before_global():
    await bot.wait_until_ready()

@bot.command()
@commands.cooldown(1, 30, commands.BucketType.user)
async def szenginler(ctx):

    toplam_para = []

    for member in ctx.guild.members:

        info = collection.find_one({"_id": str(member.id)})
        if not info:
            continue

        toplam = info.get("para", 0) + info.get("banka", 0)

        premium_tag = "⭐ " if is_premium(info) else ""

        toplam_para.append((premium_tag + member.name, toplam))

    sirali = sorted(toplam_para, key=lambda x: x[1], reverse=True)[:10]

    text = ""

    for i, (name, bakiye) in enumerate(sirali, 1):

        crown = "👑 " if i == 1 else ""

        text += f"{crown}{i}. {name} - {formatla(bakiye)} EwoCoin\n"

    embed = discord.Embed(
        title=f"💰 {ctx.guild.name} En Zenginler",
        description=text or "Veri yok",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)

# ------------------- q!enflasyon -------------------
@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def enflasyon(ctx):

    oran = enflasyon_orani()
    toplam = global_toplam_para()

    embed = discord.Embed(title="📈 Ekonomi Durumu", color=discord.Color.orange())
    embed.add_field(name="Toplam Para", value=f"{formatla(toplam)} EwoCoin", inline=False)
    embed.add_field(name="Enflasyon Oranı", value=f"{round(oran,2)}x", inline=False)

    await ctx.send(embed=embed)

# =====================================================
# 📈 ENFLASYON OTOMATİK (SAFE VERSION)
# =====================================================

ENFLASYON_KANAL_ID = 1479627407978795191
enflasyon_mesaj_id = None


@tasks.loop(hours=1)
async def enflasyon_gonder():
    global enflasyon_mesaj_id

    try:
        kanal = bot.get_channel(ENFLASYON_KANAL_ID)
        if not kanal:
            print("Enflasyon kanalı bulunamadı.")
            return

        toplam = global_toplam_para()
        oran = enflasyon_orani()

        embed = discord.Embed(
            title="📈 Güncel Enflasyon",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Toplam Dolaşımdaki Para",
            value=f"💸 {formatla(toplam)} EwoCoin",
            inline=False
        )

        embed.add_field(
            name="Enflasyon Oranı",
            value=f"{round(oran,2)}x",
            inline=False
        )

        # Mesaj varsa edit
        if enflasyon_mesaj_id:
            try:
                mesaj = await kanal.fetch_message(enflasyon_mesaj_id)
                await mesaj.edit(embed=embed)
                return
            except:
                enflasyon_mesaj_id = None

        # Yoksa yeni oluştur
        mesaj = await kanal.send(embed=embed)
        enflasyon_mesaj_id = mesaj.id

    except Exception as e:
        print("Enflasyon hata:", e)


@enflasyon_gonder.before_loop
async def before_enflasyon():
    await bot.wait_until_ready()

# ------------------- q!soygun -------------------
@bot.command()
@commands.cooldown(1, 500, commands.BucketType.user)
async def soygun(ctx, member: discord.Member):

    if member.bot:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Botu soyamazsın.")

    if member == ctx.author:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Kendini soyamazsın.")

    soyguncu = get_user(ctx.author.id)
    hedef = get_user(member.id)

    if soyguncu["para"] < 5000:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Soygun için en az 5.000 EwoCoin lazım!")

    if hedef["para"] < 10000:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Bu kişinin soyulacak kadar nakit parası yok!")

    # --- Boost Kontrolleri ---
    silah_var = soyguncu["envanter"].get("Silah", 0) > 0
    koruma_var = hedef["envanter"].get("Özel Koruma", 0) > 0

    basari_orani = 0.30
    calma_orani = 0.25

    if silah_var:
        basari_orani += 0.50
        calma_orani += 0.10

    if koruma_var:
        basari_orani -= 0.25
        calma_orani -= 0.10

    basari_orani = max(0.05, min(basari_orani, 0.95))
    calma_orani = max(0.05, min(calma_orani, 0.50))

    # --- Soygun Denemesi ---
    if random.random() < basari_orani:

        kazanilan = max(500, int(hedef["para"] * calma_orani))

        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"para": -kazanilan}}
        )

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanilan}}
        )

        sonuc = (
            f"💰 **Soygun Başarılı!**\n"
            f"{ctx.author.mention}, {member.mention}'den "
            f"**{formatla(kazanilan)} EwoCoin** çaldın!"
        )

    else:

        ceza = 2000

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": -ceza}}
        )

        sonuc = (
            f"💀 **Soygun Başarısız!**\n"
            f"Polis seni yakaladı ve **{formatla(ceza)} EwoCoin** ceza kesti!"
        )

    # --- Boost Düşürme ---
    update_dict = {}

    if silah_var:
        update_dict["envanter.Silah"] = -1

    if update_dict:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": update_dict}
        )

    if koruma_var:
        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"envanter.Özel Koruma": -1}}
        )

    await ctx.send(sonuc)
    await xp_ekle(ctx.author.id, 20)
    await ewopass_xp_ekle(ctx.author.id, 5)

# ------------------- ADMIN KOMUTLARI -------------------
ADMIN_ID = 1271933410251772017
kilitli_kanallar = set()

# ---------------- q!kitle / q!kitleaç ----------------
kilitli_kanallar = set()

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def kitle(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send('❌ Bu komutu kullanamazsın!')

    kilitli_kanallar.add(ctx.channel.id)
    await ctx.send(f'🔒 Bu kanalda EwoBot komutları devre dışı bırakıldı.')

@bot.command()
async def kitleaç(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send('❌ Bu komutu kullanamazsın!')

    kilitli_kanallar.discard(ctx.channel.id)
    await ctx.send(f'🔓 Bu kanalda EwoBot komutları tekrar aktif edildi.')

@bot.check
async def kanal_kontrol(ctx):
    if ctx.channel.id in kilitli_kanallar and ctx.author.id != ADMIN_ID:
        return False
    return True

@bot.command()
async def paraekle(ctx, member: discord.Member, miktar: int):
    if ctx.author.id != ADMIN_ID:
        return

    collection.update_one(
        {"_id": str(member.id)},
        {"$inc": {"para": miktar}}
    )

    await ctx.send("✅ Para eklendi.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def parasil(ctx, member: discord.Member, miktar: int):
    if ctx.author.id != ADMIN_ID:
        return

    collection.update_one(
        {"_id": str(member.id)},
        {"$inc": {"para": -miktar}}
    )

    await ctx.send("✅ Para silindi.")

# ------------------ BAKIM MODU ------------------
KANAL_ID = 1474489287859769656  # Mesaj atılacak kanal
SUNUCU_ID = 1471843922115301493  # Belirtilen sunucu

@bot.command()
async def bakımbaslat(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ Bu komutu kullanamazsın!")

    kanal = bot.get_channel(KANAL_ID)
    if kanal and ctx.guild.id == SUNUCU_ID:
        await kanal.send("@everyone ⚠️ EwoBot bakıma alınmıştır bilginize!")

    await ctx.send("✅ Bakım modu aktif! Kanal bilgilendirildi.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def bakımbitti(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ Bu komutu kullanamazsın!")

    kanal = bot.get_channel(KANAL_ID)
    if kanal and ctx.guild.id == SUNUCU_ID:
        await kanal.send("@everyone ✅ EwoBotun bakımı bitmiştir, Bot tekrardan aktif!")

    await ctx.send("✅ Bakım modu sonlandırıldı! Kanal bilgilendirildi.")

# ---------------- DUYURU SİSTEMİ ; ----------------------

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def duyuru(ctx, kanal: discord.TextChannel, *, mesaj):
    if ctx.author.id != 1271933410251772017:
        return

    await kanal.send(mesaj)
    await ctx.send("✅ Duyuru gönderildi.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def embedduyuru(ctx, kanal: discord.TextChannel, *, mesaj):
    if ctx.author.id != 1271933410251772017:
        return

    embed = discord.Embed(
        title="📢 EwoBot Resmi Duyuru",
        description=mesaj,
        color=discord.Color.dark_blue()
    )

    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="EwoBot Yönetimi | Resmi Duyuru")

    await kanal.send(embed=embed)
    await ctx.send("✅ Embed duyuru gönderildi.")

import asyncio

@bot.command()
async def onemliduyuru(ctx, *, mesaj):

    if ctx.author.id != 1271933410251772017:
        return

    tum_kullanicilar = [int(user["_id"]) for user in collection.find({}, {"_id": 1})]
    toplam = len(tum_kullanicilar)

    onay_embed = discord.Embed(
        title="⚠️ Duyuru Onayı",
        description=(
            f"Bu duyuru **{toplam} kullanıcıya** gönderilecek.\n\n"
            f"**Mesaj:**\n{mesaj}\n\n"
            f"Devam etmek için **evet** yaz.\n"
            f"İptal etmek için **hayır** yaz."
        ),
        color=discord.Color.orange()
    )

    await ctx.send(embed=onay_embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        cevap = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Süre doldu. Duyuru iptal edildi.")
        return

    if cevap.content.lower() != "evet":
        await ctx.send("❌ Duyuru iptal edildi.")
        return

    baslangic = time.time()

    duyuru_embed = discord.Embed(
        title="🚨 EwoBot Önemli Duyuru",
        description=mesaj,
        color=discord.Color.dark_blue()
    )

    duyuru_embed.set_thumbnail(url=bot.user.avatar.url)
    duyuru_embed.set_footer(text="EwoBot Yönetimi")

    ilerleme_embed = discord.Embed(
        title="📡 Duyuru Gönderiliyor...",
        description=f"👥 Toplam Kullanıcı: **{toplam}**\n📨 Başarılı: **0**\n❌ Başarısız: **0**",
        color=discord.Color.dark_blue()
    )

    mesaj_obj = await ctx.send(embed=ilerleme_embed)

    basarili = 0
    basarisiz = 0

    semaphore = asyncio.Semaphore(10)

    async def dm_gonder(user_id):
        nonlocal basarili, basarisiz

        async with semaphore:
            try:
                uye = await bot.fetch_user(user_id)
                await uye.send(embed=duyuru_embed)
                basarili += 1
            except:
                basarisiz += 1

    gorevler = [asyncio.create_task(dm_gonder(uid)) for uid in tum_kullanicilar]

    for i, task in enumerate(asyncio.as_completed(gorevler), start=1):

        await task

        if i % 20 == 0 or i == toplam:

            ilerleme_embed.description = (
                f"👥 Toplam Kullanıcı: **{toplam}**\n"
                f"📨 Başarılı: **{basarili}**\n"
                f"❌ Başarısız: **{basarisiz}**\n"
                f"📊 Gönderilen: **{i}/{toplam}**"
            )

            await mesaj_obj.edit(embed=ilerleme_embed)

    toplam_sure = int(time.time() - baslangic)

    final_embed = discord.Embed(
        title="📊 Duyuru Tamamlandı",
        description=(
            f"👥 Toplam Kullanıcı: **{toplam}**\n\n"
            f"📨 Başarılı: **{basarili}**\n"
            f"❌ Başarısız: **{basarisiz}**\n\n"
            f"⏱ Süre: **{toplam_sure} saniye**"
        ),
        color=discord.Color.green()
    )

    await mesaj_obj.edit(embed=final_embed)

# ===============================
# YENİ INVITE OLUŞURSA CACHE GÜNCELLE
# ===============================
@bot.event
async def on_invite_create(invite):
    try:
        invites = await invite.guild.invites()
        invite_cache[invite.guild.id] = invites
    except Exception as e:
        print(f"Invite güncelleme hatası: {e}")

MILESTONES = {
    25: 5000,
    50: 10000,
    100: 20000,
    200: 30000,
    500: 40000,
    1000: 50000
}

MILESTONE_KANAL = 1474497995297918976
BOT_LOG_KANAL = 1474500594554372247

# =====================================================
# SUNUCUYA EKLENİNCE
# =====================================================
@bot.event
async def on_guild_join(guild):
    await bot.wait_until_ready()

    toplam = len(bot.guilds)
    print(f"Yeni sunucu: {guild.name} | Toplam: {toplam}")

    inviter = "Bilinmiyor"

    # 🔎 Invite Tracking
    try:
        new_invites = await guild.invites()
        old_invites = invite_cache.get(guild.id, [])

        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = f"{new_inv.inviter} ({new_inv.inviter.id})"

        invite_cache[guild.id] = new_invites

    except Exception as e:
        print(f"Invite kontrol hatası: {e}")

    # 👑 Owner
    try:
        owner = guild.owner
        owner_text = f"{owner} ({owner.id})"
    except:
        owner_text = "Bilinmiyor"

    icon_url = guild.icon.url if guild.icon else None

    # =================================================
    # LOG EMBED
    # =================================================
    log_kanal = bot.get_channel(BOT_LOG_KANAL)

    if log_kanal:
        embed = discord.Embed(
            title="✅ EwoBot Yeni Sunucuya Eklendi",
            color=discord.Color.green()
        )

        embed.add_field(name="📌 Sunucu", value=guild.name, inline=False)
        embed.add_field(name="🆔 Sunucu ID", value=guild.id, inline=False)
        embed.add_field(name="👥 Üye Sayısı", value=guild.member_count, inline=False)
        embed.add_field(name="👑 Sunucu Sahibi", value=owner_text, inline=False)
        embed.add_field(name="🚀 Botu Ekleyen", value=inviter, inline=False)
        embed.add_field(name="📊 Toplam Sunucu", value=toplam, inline=False)

        if icon_url:
            embed.set_thumbnail(url=icon_url)

        await log_kanal.send(embed=embed)

    # =================================================
    # MILESTONE SİSTEMİ
    # =================================================
    milestone_kanal = bot.get_channel(MILESTONE_KANAL)
    if not milestone_kanal:
        return

    data = settings_col.find_one({"_id": "milestone_system"}) or {"last_reached": 0}
    last_reached = data.get("last_reached", 0)

    if toplam > last_reached:
        for hedef, odul in sorted(MILESTONES.items()):
            if last_reached < hedef <= toplam:

                print(f"🎯 Milestone tetiklendi: {hedef}")

                try:
                    result = collection.update_many({}, {"$inc": {"banka": odul}})
                    print(f"{result.modified_count} kullanıcıya ödül verildi")
                except Exception as e:
                    print("Ödül yatırma hatası:", e)

                milestone_embed = discord.Embed(
                    title=f"🚀 EWO BOT ARTIK {hedef} SUNUCUDA!",
                    description=(
                        f"💚 Destekleyen herkese teşekkürler!\n\n"
                        f"🎁 Tüm kullanıcılara {odul:,} EwoCoin hediye edildi!"
                    ),
                    color=discord.Color.gold()
                )

                await milestone_kanal.send(embed=milestone_embed)

                settings_col.update_one(
                    {"_id": "milestone_system"},
                    {"$set": {"last_reached": hedef}},
                    upsert=True
                )


# =====================================================
# SUNUCUDAN ÇIKINCA
# =====================================================
@bot.event
async def on_guild_remove(guild):

    invite_cache.pop(guild.id, None)

    kanal = bot.get_channel(BOT_LOG_KANAL)
    if not kanal:
        return

    embed = discord.Embed(
        title="❌ EwoBot Bir Sunucudan Çıkarıldı",
        color=discord.Color.red()
    )

    embed.add_field(name="Sunucu", value=guild.name, inline=False)
    embed.add_field(name="Sunucu ID", value=guild.id, inline=False)
    embed.add_field(name="Kalan Sunucu Sayısı", value=len(bot.guilds), inline=False)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await kanal.send(embed=embed)

TICKET_ADMIN_ID = 1271933410251772017
TICKET_LOG_KANAL = 1474500533405487155 # ticket formları düşecek kanal

class TicketModal(discord.ui.Modal):

    def __init__(self, kategori):
        super().__init__(title=f"{kategori} Formu")
        self.kategori = kategori

        self.sorun = discord.ui.TextInput(
            label="Sorununuzu Açıklayın",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        )

        self.not_alani = discord.ui.TextInput(
            label="Not (Opsiyonel)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )

        self.add_item(self.sorun)
        self.add_item(self.not_alani)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        log_kanal = interaction.client.get_channel(TICKET_LOG_KANAL)

        if not log_kanal:
            return await interaction.response.send_message(
                "❌ Log kanalı bulunamadı.",
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"📩 Yeni {self.kategori} Formu",
            color=discord.Color.dark_blue()
        )

        embed.set_thumbnail(url=user.avatar.url if user.avatar else None)
        embed.add_field(name="Kullanıcı ID", value=user.id, inline=False)
        embed.add_field(name="Kullanıcı Adı", value=f"{user} ({user.display_name})", inline=False)
        embed.add_field(name="Sorun", value=self.sorun.value, inline=False)
        embed.add_field(name="Not", value=self.not_alani.value or "Yok", inline=False)
        embed.set_footer(text="EwoBot | EwoBot Destek Sistemi")
        embed.timestamp = datetime.datetime.now()

        view = TicketCevapView(user.id)

        await log_kanal.send(embed=embed, view=view)

        # ✅ BOT PROFİLLİ DM
        dm_embed = discord.Embed(
            title="✅ Formunuz Gönderildi",
            description="Yetkili ekibimiz kısa süre içinde sizinle iletişime geçecektir.",
            color=discord.Color.dark_blue()
        )

        dm_embed.set_author(
            name=str(interaction.client.user),
            icon_url=interaction.client.user.avatar.url
        )

        dm_embed.set_thumbnail(url=interaction.client.user.avatar.url)
        dm_embed.set_footer(text="EwoBot | EwoBot Destek Sistemi")
        dm_embed.timestamp = datetime.datetime.now()

        try:
            await user.send(embed=dm_embed)
        except:
            pass

        await interaction.response.send_message("✅ Form başarıyla gönderildi.", ephemeral=True)

class TicketCevapView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(
            label="Cevapla",
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket_cevap_{user_id}"
        ))

class TicketCevapModal(discord.ui.Modal):

    def __init__(self, user_id):
        super().__init__(title="Destek Cevabı")
        self.user_id = user_id

        self.cevap = discord.ui.TextInput(
            label="Cevabınızı Yazın",
            style=discord.TextStyle.paragraph,
            required=True
        )

        self.add_item(self.cevap)

    async def on_submit(self, interaction: discord.Interaction):
        user = await interaction.client.fetch_user(self.user_id)

        embed = discord.Embed(
            title="📨 Destek Cevabı",
            description=self.cevap.value,
            color=discord.Color.dark_blue()
        )

        # Küçük yetkili profili
        embed.set_author(
            name=f"{interaction.user} (Yetkili)",
            icon_url=interaction.user.avatar.url
        )

        # Büyük bot profili
        embed.set_thumbnail(url=interaction.client.user.avatar.url)

        embed.set_footer(text="EwoBot | EwoBot Destek Sistemi")
        embed.timestamp = datetime.datetime.now()

        try:
            await user.send(embed=embed)
            await interaction.response.send_message("✅ Kullanıcıya gönderildi.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Kullanıcıya DM gönderilemedi.", ephemeral=True)

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def ticketat(ctx):
    if ctx.author.id != TICKET_ADMIN_ID:
        return await ctx.send("❌ Bu komutu kullanamazsın!")

    embed = discord.Embed(
        title="📩 EwoBot Destek Sistemi",
        description=(
            "Merhaba! Destek sistemine hoş geldin.\n"
            "Aşağıdan ihtiyacına uygun kategori seçerek destek talebi oluşturabilirsin.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📜 **Talimatlar**\n"
            "Aşağıdaki kategorilerden birini seç.\n\n"
            "🤖 **Bot Destek**\n"
            "Bot ile ilgili yaşadığınız teknik sorunlar için.\n\n"
            "⚖️ **Oyuncu Şikayet**\n"
            "Başka bir oyuncu hakkında şikayet oluşturmak için.\n\n"
            "🐞 **Bug Bildiri**\n"
            "Sunucu veya bot ile ilgili hata bildirmek için.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=discord.Color.dark_blue()
    )

    embed.set_author(
        name=str(bot.user),
        icon_url=bot.user.avatar.url
    )

    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="EwoBot Destek Sistemi")
    embed.timestamp = datetime.datetime.now()

    await ctx.send(embed=embed, view=TicketPanelView())



class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bot Destek", style=discord.ButtonStyle.primary, custom_id="ticket_botdestek")
    async def bot_destek(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Bot Destek"))

    @discord.ui.button(label="Oyuncu Şikayet", style=discord.ButtonStyle.secondary, custom_id="ticket_sikayet")
    async def oyuncu_sikayet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Oyuncu Şikayet"))

    @discord.ui.button(label="Bug Bildiri", style=discord.ButtonStyle.success, custom_id="ticket_bug")
    async def bug_bildiri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal("Bug Bildiri"))

# =====================================================
# 🔥 EWO FULL ADMIN PANEL SYSTEM (STABLE VERSION)
# =====================================================

ADMIN_ID = 1271933410251772017
BAKIM_KANAL_ID = 1474489287859769656
EKONOMI_LOG_KANAL = 1479627767111876759

# =====================================================
# YARDIMCI FONKSİYON
# =====================================================

def parse_int(value: str):
    return int(value.replace(".", "").replace(",", "").strip())

# =====================================================
# ANA KOMUT
# =====================================================

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def adminpaneli(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ Bu komut sadece bot sahibine özeldir.")
    await ctx.send(embed=admin_main_embed(), view=AdminMainView())

def admin_main_embed():
    embed = discord.Embed(
        title="⚙️ EwoBot Admin Paneli",
        description="💰 Ekonomi & Para\n🔒 Kanal Kontrol\n🛠 Bakım Modu",
        color=discord.Color.dark_blue()
    )
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    return embed

# =====================================================
# ANA VIEW
# =====================================================

class AdminMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Ekonomi & Para", style=discord.ButtonStyle.primary)
    async def ekonomi(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="💰 Ekonomi Yönetimi", color=discord.Color.dark_blue()),
            view=EkonomiView()
        )

    @discord.ui.button(label="🔒 Kanal Kontrol", style=discord.ButtonStyle.secondary)
    async def kanal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🔒 Kanal Kontrol", color=discord.Color.dark_blue()),
            view=KanalView()
        )

    @discord.ui.button(label="🛠 Bakım Modu", style=discord.ButtonStyle.danger)
    async def bakim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="🛠 Bakım Modu", color=discord.Color.dark_blue()),
            view=BakimView()
        )

# =====================================================
# EKONOMİ GÜNCELLE MODAL (TEK MODAL - STABLE)
# =====================================================

class EkonomiDegistirModal(discord.ui.Modal, title="Ekonomi Güncelle"):

    def __init__(self):
        super().__init__(timeout=None)

        self.varliklar = list(varsayilan_varlikler.keys())

        metin = ""

        for varlik in self.varliklar:
            data = economy_col.find_one({"_id": varlik})
            eski = data["current_price"] if data else varsayilan_varlikler.get(varlik, 0)
            metin += f"{varlik}={eski}\n"

        self.add_item(
            discord.ui.TextInput(
                label="Varlık Fiyatları (örnek: Altin=5000)",
                style=discord.TextStyle.paragraph,
                default=metin,
                required=True,
                max_length=2000
            )
        )

    async def on_submit(self, interaction: discord.Interaction):

        try:
            satirlar = self.children[0].value.split("\n")

            embed = discord.Embed(
                title="📊 EwoEkonomi Güncellendi!",
                color=discord.Color.dark_blue()
            )

            for satir in satirlar:

                if "=" not in satir:
                    continue

                varlik, fiyat = satir.split("=")

                varlik = varlik.strip()
                yeni_fiyat = int(fiyat.replace(".", "").replace(",", "").strip())

                eski_data = economy_col.find_one({"_id": varlik})
                eski = eski_data["current_price"] if eski_data else 0

                economy_col.update_one(
                    {"_id": varlik},
                    {"$set": {"current_price": yeni_fiyat}},
                    upsert=True
                )

                fark = yeni_fiyat - eski

                if fark > 0:
                    durum = f"🟢 +{formatla(fark)}"
                elif fark < 0:
                    durum = f"🔴 -{formatla(abs(fark))}"
                else:
                    durum = "⚪ Değişim yok"

                embed.add_field(
                    name=f"{varlik} ({durum})",
                    value=f"Eski: {formatla(eski)}\nYeni: {formatla(yeni_fiyat)}",
                    inline=False
                )

            if interaction.client.user.avatar:
                embed.set_thumbnail(url=interaction.client.user.avatar.url)

            embed.set_footer(text="EwoBot Global Ekonomi Sistemi")

            kanal = interaction.client.get_channel(EKONOMI_LOG_KANAL)
            if kanal:
                await kanal.send(embed=embed)

            await interaction.response.send_message(
                "✅ Ekonomi başarıyla güncellendi.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Hata oluştu: {str(e)}",
                ephemeral=True
            )
# =====================================================
# EKONOMİ VIEW
# =====================================================

class EkonomiView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Faiz Yatır (%5)", style=discord.ButtonStyle.primary)
    async def faiz(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        for user in collection.find():
            banka = user.get("banka", 0)
            faiz = int(banka * 0.05)
            collection.update_one({"_id": user["_id"]}, {"$inc": {"banka": faiz}})

        await interaction.followup.send("✅ Faiz yatırıldı.", ephemeral=True)

    @discord.ui.button(label="Maaş Yatır", style=discord.ButtonStyle.primary)
    async def maas(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.defer(ephemeral=True)

        for user in collection.find():
            meslek = user.get("meslek", "İşsiz")
            maas = meslekler.get(meslek, {}).get("maas", 0)
            collection.update_one({"_id": user["_id"]}, {"$inc": {"banka": maas}})

        await interaction.followup.send("✅ Maaş yatırıldı.", ephemeral=True)

    @discord.ui.button(label="Ekonomi Değiştir", style=discord.ButtonStyle.success)
    async def degistir(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EkonomiDegistirModal())

    @discord.ui.button(label="Ekonomi Sıfırla", style=discord.ButtonStyle.danger)
    async def sifirla(self, interaction: discord.Interaction, button: discord.ui.Button):

        for varlik, fiyat in varsayilan_varlikler.items():
            economy_col.update_one(
                {"_id": varlik},
                {"$set": {"current_price": fiyat}},
                upsert=True
            )

        await interaction.response.send_message("💰 Ekonomi sıfırlandı.", ephemeral=True)

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=admin_main_embed(), view=AdminMainView())

# =====================================================
# KANAL VIEW
# =====================================================

class KanalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Kitle", style=discord.ButtonStyle.danger)
    async def kitle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message("🔒 Kanal kilitlendi.", ephemeral=True)

    @discord.ui.button(label="Kitle Aç", style=discord.ButtonStyle.success)
    async def ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message("🔓 Kanal açıldı.", ephemeral=True)

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=admin_main_embed(), view=AdminMainView())

# =====================================================
# BAKIM SİSTEMİ
# =====================================================

@bot.check
async def global_bakim_kontrol(ctx):

    data = settings_col.find_one({"_id": "global"})

    if data and data.get("bakim_modu"):

        # Sadece izinli 2 kişi kullanabilir
        izinli_kullanicilar = [
            1271933410251772017,
            1391502292934590539
        ]

        if ctx.author.id in izinli_kullanicilar:
            return True

        embed = discord.Embed(
            title="🛠 EwoBot Bakımda",
            description="Şu anda komut kullanamazsınız!\nLütfen bakımın bitmesini bekleyin.",
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)
        return False

    return True

class BakimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bakım Başlat", style=discord.ButtonStyle.danger)
    async def baslat(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings_col.update_one({"_id": "global"}, {"$set": {"bakim_modu": True}}, upsert=True)
        await interaction.response.send_message("✅ Bakım başlatıldı.", ephemeral=True)

    @discord.ui.button(label="Bakım Bitir", style=discord.ButtonStyle.success)
    async def bitir(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings_col.update_one({"_id": "global"}, {"$set": {"bakim_modu": False}}, upsert=True)
        await interaction.response.send_message("✅ Bakım kapatıldı.", ephemeral=True)

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=admin_main_embed(), view=AdminMainView())

# =====================================================
# 🌍 OTOMATİK EKONOMİ SİSTEMİ (2 SAATTE BİR)
# =====================================================

@tasks.loop(hours=2)
async def otomatik_ekonomi():

    kanal = bot.get_channel(EKONOMI_LOG_KANAL)
    if not kanal:
        return

    embed = discord.Embed(
        title="📊 EwoEkonomi Güncellendi!",
        color=discord.Color.dark_blue()
    )

    for varlik, referans in varsayilan_varlikler.items():

        data = economy_col.find_one({"_id": varlik})
        eski = data["current_price"] if data else referans

        fark_orani = (eski - referans) / referans

        # 🔥 Aşırı yükselmişse sert düşüş ihtimali
        if fark_orani > 0.50:
            degisim_yuzde = random.uniform(-0.25, -0.10)

        # 🔥 Aşırı düşmüşse sert toparlanma
        elif fark_orani < -0.50:
            degisim_yuzde = random.uniform(0.10, 0.25)

        # 🔥 Normal dalgalanma
        else:
            degisim_yuzde = random.uniform(-0.10, 0.10)

        degisim = int(eski * degisim_yuzde)
        yeni = eski + degisim

        # 🔒 Daha geniş sınırlar
        minimum = int(referans * 0.20)
        maximum = int(referans * 6)

        if yeni < minimum:
            yeni = minimum
        if yeni > maximum:
            yeni = maximum

        economy_col.update_one(
            {"_id": varlik},
            {"$set": {"current_price": yeni}},
            upsert=True
        )

        fark = yeni - eski

        if fark > 0:
            durum = f"🟢 +{formatla(fark)}"
        elif fark < 0:
            durum = f"🔴 -{formatla(abs(fark))}"
        else:
            durum = "⚪ Değişim yok"

        embed.add_field(
            name=f"{varlik} ({durum})",
            value=f"Eski: {formatla(eski)}\nYeni: {formatla(yeni)}",
            inline=False
        )

    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)

    embed.set_footer(text="EwoBot Global Ekonomi Sistemi")

    await kanal.send(embed=embed)

# =====================================================
# 🛒 MARKET SİSTEMİ
# =====================================================

MARKET_URUNLERI = {

    "Bronz Kasa": {"fiyat": 500},
    "Gümüş Kasa": {"fiyat": 2000},
    "Altın Kasa": {"fiyat": 5000},
    "Elmas Kasa": {"fiyat": 15000},
    "Premium Kasa": {"fiyat": 30000},
    "EwoPlus Kasa": {"fiyat": 60000},

    "Silah": {"fiyat": 15000},
    "Özel Koruma": {"fiyat": 20000},

    "Olta": {"fiyat": 1000},
    "Yüzük": {"fiyat": 75000},

    "Bronz Görünüş": {"fiyat": 500000},
    "Gümüş Görünüş": {"fiyat": 2000000},
    "Altın Görünüş": {"fiyat": 5000000},
    "Elmas Görünüş": {"fiyat": 15000000},

    "Özel Araçgereçler": {"fiyat": 750000}

}

@bot.command()
async def market(ctx):

    embed = market_ana_embed()
    embed.set_thumbnail(url=bot.user.avatar.url)

    await ctx.send(
        embed=embed,
        view=MarketMainView()
    )

def market_ana_embed():

    return discord.Embed(
        title="🛒 EwoBot Market",
        description="Kategori seç:",
        color=discord.Color.dark_blue()
    )

# =====================================================
# ANA MENÜ
# =====================================================

class MarketMainView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎁 Kasa", style=discord.ButtonStyle.primary)
    async def kasa(self, interaction, button):

        await interaction.response.edit_message(
            embed=kasa_embed(),
            view=KasaView()
        )

    @discord.ui.button(label="🕶 Soygun", style=discord.ButtonStyle.danger)
    async def soygun(self, interaction, button):

        await interaction.response.edit_message(
            embed=soygun_embed(),
            view=SoygunView()
        )

    @discord.ui.button(label="🎣 Ekonomi", style=discord.ButtonStyle.success)
    async def ekonomi(self, interaction, button):

        await interaction.response.edit_message(
            embed=ekonomii_embed(),
            view=EkonomiiView()
        )

    @discord.ui.button(label="👑 Gösteriş", style=discord.ButtonStyle.secondary)
    async def gosteris(self, interaction, button):

        await interaction.response.edit_message(
            embed=gosteris_embed(),
            view=GosterisView()
        )

# =====================================================
# EMBEDLER
# =====================================================

def kasa_embed():
    return discord.Embed(
        title="🎁 Kasa Marketi",
        description=
        "Bronz Kasa - 500\n"
        "Gümüş Kasa - 2000\n"
        "Altın Kasa - 5000\n"
        "Elmas Kasa - 15000\n"
        "Premium Kasa - 30000\n"
        "EwoPlus Kasa - 60000",
        color=discord.Color.gold()
    )

def soygun_embed():
    return discord.Embed(
        title="🕶 Soygun Marketi",
        description=
        "Silah - 15000\n"
        "Özel Koruma - 20000\n"
        "Özel Araçgereçler - 750000",
        color=discord.Color.red()
    )

def ekonomii_embed():
    return discord.Embed(
        title="🎣 Ekonomi Marketi",
        description=
        "Olta - 1000\n"
        "Yüzük - 75000",
        color=discord.Color.green()
    )

def gosteris_embed():
    return discord.Embed(
        title="👑 Gösteriş Marketi",
        description=
        "Bronz Görünüş - 500000\n"
        "Gümüş Görünüş - 2000000\n"
        "Altın Görünüş - 5000000\n"
        "Elmas Görünüş - 15000000",
        color=discord.Color.purple()
    )

# =====================================================
# VIEWLER
# =====================================================

class KasaView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bronz Kasa", style=discord.ButtonStyle.primary)
    async def bronz(self, interaction, button):
        await satin_al(interaction,"Bronz Kasa")

    @discord.ui.button(label="Gümüş Kasa", style=discord.ButtonStyle.primary)
    async def gumus(self, interaction, button):
        await satin_al(interaction,"Gümüş Kasa")

    @discord.ui.button(label="Altın Kasa", style=discord.ButtonStyle.primary)
    async def altin(self, interaction, button):
        await satin_al(interaction,"Altın Kasa")

    @discord.ui.button(label="Elmas Kasa", style=discord.ButtonStyle.primary)
    async def elmas(self, interaction, button):
        await satin_al(interaction,"Elmas Kasa")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):

        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )

class SoygunView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Silah", style=discord.ButtonStyle.danger)
    async def silah(self, interaction, button):
        await satin_al(interaction,"Silah")

    @discord.ui.button(label="Özel Koruma", style=discord.ButtonStyle.danger)
    async def koruma(self, interaction, button):
        await satin_al(interaction,"Özel Koruma")

    @discord.ui.button(label="Özel Araçgereçler", style=discord.ButtonStyle.danger)
    async def arac(self, interaction, button):
        await satin_al(interaction,"Özel Araçgereçler")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):

        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )

class EkonomiiView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Olta", style=discord.ButtonStyle.success)
    async def olta(self, interaction, button):
        await satin_al(interaction,"Olta")

    @discord.ui.button(label="Yüzük", style=discord.ButtonStyle.success)
    async def yuzuk(self, interaction, button):
        await satin_al(interaction,"Yüzük")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):

        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )

class GosterisView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bronz Görünüş", style=discord.ButtonStyle.secondary)
    async def bronz(self, interaction, button):
        await satin_al(interaction,"Bronz Görünüş")

    @discord.ui.button(label="Gümüş Görünüş", style=discord.ButtonStyle.secondary)
    async def gumus(self, interaction, button):
        await satin_al(interaction,"Gümüş Görünüş")

    @discord.ui.button(label="Altın Görünüş", style=discord.ButtonStyle.secondary)
    async def altin(self, interaction, button):
        await satin_al(interaction,"Altın Görünüş")

    @discord.ui.button(label="Elmas Görünüş", style=discord.ButtonStyle.secondary)
    async def elmas(self, interaction, button):
        await satin_al(interaction,"Elmas Görünüş")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):

        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )

# =====================================================
# SATIN AL
# =====================================================

async def satin_al(interaction, urun):

    user = get_user(interaction.user.id)

    fiyat = MARKET_URUNLERI[urun]["fiyat"]

    if user["para"] < fiyat:

        return await interaction.response.send_message(
            "❌ Paran yetmiyor.",
            ephemeral=True
        )

    collection.update_one(
        {"_id": str(interaction.user.id)},
        {
            "$inc":{
                "para":-fiyat,
                f"envanter.{urun}":1
            }
        }
    )

    await interaction.response.send_message(
        f"✅ {urun} satın alındı!",
        ephemeral=True
    )

# Envanter Komutu
@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def envanter(ctx):

    user = get_user(ctx.author.id)
    envanter = user.get("envanter", {})

    if not envanter:
        embed = discord.Embed(
            title="🎒 Envanterin",
            description="Envanter boş.",
            color=discord.Color.dark_blue()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        return await ctx.send(embed=embed)

    text = ""

    for urun, adet in envanter.items():

        if adet <= 0:
            continue

        # Ürün ikonları
        if urun == "Yüzük":
            icon = "💍"
        elif "Kasa" in urun:
            icon = "🎁"
        elif urun == "Silah":
            icon = "🔫"
        elif urun == "Özel Koruma":
            icon = "🛡"
        elif urun == "Olta":
            icon = "🎣"
        else:
            icon = "📦"

        text += f"{icon} {urun} x{adet}\n"

    if text == "":
        text = "Envanter boş."

    embed = discord.Embed(
        title="🎒 Envanterin",
        description=text,
        color=discord.Color.dark_blue()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.set_footer(text="💡 Marketten yeni eşyalar alarak envanterini genişletebilirsin.")

    await ctx.send(embed=embed)

# balık tutma 
@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def balıktut(ctx):

    user = get_user(ctx.author.id)
    oltali = user.get("envanter", {}).get("Olta", 0) > 0

    oranlar = {
        "Bronz": 60,
        "Gümüş": 30,
        "Altın": 20,
        "Elmas": 7,
        "Efsanevi": 3
    }

    if oltali:
        oranlar["Altın"] += 10
        oranlar["Elmas"] += 10
        oranlar["Efsanevi"] += 20

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"envanter.Olta": -1}}
        )

    balık = random.choices(
        population=list(oranlar.keys()),
        weights=list(oranlar.values())
    )[0]

    degerler = {
        "Bronz": 200,
        "Gümüş": 500,
        "Altın": 1000,
        "Elmas": 1750,
        "Efsanevi": 2250
    }

    kazanc = degerler[balık]

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": kazanc}}
    )

    if oltali:
        await ctx.send(f"🎣 Olta sayesinde {balık} Balık tuttun! +{formatla(kazanc)}")
    else:
        await ctx.send(f"🎣 {balık} Balık tuttun! +{formatla(kazanc)}")

    await xp_ekle(ctx.author.id, 5)
    await ewopass_xp_ekle(ctx.author.id, 5)

# kasa aç 
@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def kasaaç(ctx, *, kasa_adi: str):

    user = get_user(ctx.author.id)

    kasa_map = {
        "bronz": "Bronz Kasa",
        "gümüş": "Gümüş Kasa",
        "gumus": "Gümüş Kasa",
        "altın": "Altın Kasa",
        "elmas": "Elmas Kasa",
        "premium": "Premium Kasa",
        "ewoplus": "EwoPlus Kasa"
    }

    kasa_adi = kasa_adi.lower()

    if kasa_adi not in kasa_map:
        return await ctx.send("❌ Geçerli bir kasa adı gir!")

    kasa_adi = kasa_map[kasa_adi]

    if user["envanter"].get(kasa_adi, 0) <= 0:
        return await ctx.send("❌ Bu kasadan envanterinde yok!")

    kasa_oduller = {
        "Bronz Kasa": (100, 1000),
        "Gümüş Kasa": (200, 5000),
        "Altın Kasa": (400, 10000),
        "Elmas Kasa": (750, 25000),
        "Premium Kasa": (1000, 50000),
        "EwoPlus Kasa": (5000, 100000),
    }

    min_odul, max_odul = kasa_oduller[kasa_adi]
    roll = random.random()

    if roll < 0.65:
        odul = random.randint(min_odul, int(min_odul + (max_odul - min_odul) * 0.3))
    elif roll < 0.90:
        odul = random.randint(int(min_odul + (max_odul - min_odul) * 0.3),
                              int(min_odul + (max_odul - min_odul) * 0.7))
    else:
        odul = random.randint(int(min_odul + (max_odul - min_odul) * 0.7), max_odul)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "envanter." + kasa_adi: -1,
                "para": odul
            }
        }
    )

    await ctx.send(
        f"🎁 {kasa_adi} açıldı!\n"
        f"💰 İçinden **{formatla(odul)} EwoCoin** çıktı!"
    )

    await xp_ekle(ctx.author.id, 15)
    await ewopass_xp_ekle(ctx.author.id, 5)

# İŞLETME SİSTEMİ
class IsletmeSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for isim, veri in ISLETMELER.items():

            options.append(
                discord.SelectOption(
                    label=isim.capitalize(),
                    description=f"Fiyat: {formatla(veri['fiyat'])}"
                )
            )

        super().__init__(
            placeholder="İşletme seç...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )

    async def callback(self, interaction: discord.Interaction):

        secilen = self.values[0].lower()
        veri = ISLETMELER[secilen]

        embed = discord.Embed(
            title=f"🏭 {secilen.capitalize()}",
            color=discord.Color.dark_teal()
        )

        embed.add_field(
            name="💰 Fiyat",
            value=f"{formatla(veri['fiyat'])} EwoCoin",
            inline=False
        )

        embed.add_field(
            name="📈 Saatlik Gelir",
            value=f"{formatla(veri['gelir'])} EwoCoin",
            inline=False
        )

        embed.add_field(
            name="🔼 Yükseltme",
            value="Fiyat x %40 x Level",
            inline=False
        )

        embed.set_footer(text="Satın almak için: q!işletmeal <isim>")

        await interaction.response.edit_message(embed=embed, view=self.view)

class IsletmeMenu(discord.ui.View):

    def __init__(self, author):
        super().__init__(timeout=120)
        self.author = author
        self.add_item(IsletmeSelect())

    async def interaction_check(self, interaction: discord.Interaction):

        if interaction.user != self.author:
            await interaction.response.send_message(
                "❌ Bu menüyü sadece komutu kullanan kişi kullanabilir.",
                ephemeral=True
            )
            return False

        return True

@bot.command()
@commands.cooldown(1, 12, commands.BucketType.user)
async def işletmeler(ctx):

    embed = discord.Embed(
        title="🏭 İşletmeler",
        description="Aşağıdaki menüden işletme seçebilirsin.",
        color=discord.Color.dark_teal()
    )

    embed.set_thumbnail(url=bot.user.avatar.url)

    await ctx.send(embed=embed, view=IsletmeMenu(ctx.author))

# işletme top
@bot.command()
@commands.cooldown(1, 20, commands.BucketType.user)
async def işletmetop(ctx):

    users = collection.find({}, {"isletmeler": 1})
    siralama = []

    for user in users:

        toplam = 0
        isletmeler = user.get("isletmeler", {})

        for isim, veri in isletmeler.items():

            adet = veri.get("adet", 0)
            level = veri.get("level", 1)

            if isim not in ISLETMELER:
                continue

            fiyat = ISLETMELER[isim]["fiyat"]
            deger = adet * fiyat * (1 + (level - 1) * 0.20)

            toplam += deger

        siralama.append((user["_id"], int(toplam)))

    siralama = sorted(siralama, key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 Global En Büyük Sanayiciler",
        color=discord.Color.gold()
    )

    for i, (uid, deger) in enumerate(siralama, start=1):

        uye = bot.get_user(int(uid))
        isim = uye.name if uye else "Bilinmeyen"

        embed.add_field(
            name=f"#{i} {isim}",
            value=f"Toplam Değer: {formatla(deger)}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def işletmeal(ctx, isim: str, miktar: int = 1):

    isim = isim.lower()
    user = get_user(ctx.author.id)

    if isim not in ISLETMELER:
        return await ctx.send("❌ Geçersiz işletme.")

    if miktar <= 0:
        return await ctx.send("❌ Miktar 1 veya daha büyük olmalı.")

    mevcut = user.get("isletmeler", {}).get(isim, {}).get("adet", 0)

    if mevcut + miktar > 10:
        return await ctx.send("❌ Bir işletmeden en fazla **10 tane** alabilirsin.")

    temel_fiyat = ISLETMELER[isim]["fiyat"]

    toplam_fiyat = 0

    # fiyat artış sistemi
    for i in range(miktar):

        fiyat = int(temel_fiyat * (1 + (mevcut + i) * 0.40))
        toplam_fiyat += fiyat

    if user["para"] < toplam_fiyat:
        return await ctx.send(f"❌ Gerekli para: **{formatla(toplam_fiyat)}**")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": -toplam_fiyat,
                f"isletmeler.{isim}.adet": miktar
            },
            "$set": {
                f"isletmeler.{isim}.level": 1
            }
        }
    )

    sonraki_fiyat = int(temel_fiyat * (1 + (mevcut + miktar) * 0.40))

    embed = discord.Embed(
        title="🏭 İşletme Satın Alındı",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🏭 İşletme",
        value=isim.capitalize(),
        inline=True
    )

    embed.add_field(
        name="📦 Alınan",
        value=f"{miktar} adet",
        inline=True
    )

    embed.add_field(
        name="💰 Ödenen",
        value=formatla(toplam_fiyat),
        inline=False
    )

    embed.add_field(
        name="📈 Sonraki Fiyat",
        value=formatla(sonraki_fiyat),
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def işletmeyükselt(ctx, *, isim: str):

    isim = isim.lower()
    user = get_user(ctx.author.id)

    if isim not in user.get("isletmeler", {}):
        return await ctx.send("❌ Bu işletmeye sahip değilsin.")

    level = user["isletmeler"][isim].get("level", 1)

    temel = ISLETMELER[isim]["fiyat"]
    maliyet = int(temel * 0.40 * level)

    if user["para"] < maliyet:
        return await ctx.send(f"❌ Gerekli: {formatla(maliyet)}")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": -maliyet,
                f"isletmeler.{isim}.level": 1
            }
        }
    )

    await ctx.send(
        f"🔼 **{isim.capitalize()} yükseltildi!**\n"
        f"Yeni Level: {level+1}\n"
        f"Ödenen: {formatla(maliyet)}"
    )

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def sigorta(ctx):

    user = get_user(ctx.author.id)
    simdi = int(time.time())

    if user.get("sigorta_bitis", 0) > simdi:
        return await ctx.send("🛡 Sigorta zaten aktif.")

    fiyat = 500000

    if user["para"] < fiyat:
        return await ctx.send("❌ Paran yetmiyor.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": -fiyat},
            "$set": {"sigorta_bitis": simdi + 86400}
        }
    )

    await ctx.send("🛡 24 saatlik sigorta aktif edildi!")


@bot.command()
@commands.cooldown(1, 20, commands.BucketType.user)
async def işletmeparaçek(ctx):

    user = get_user(ctx.author.id)
    simdi = int(time.time())

    son = int(user.get("son_isletme_toplama", 0))

    if son == 0:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"son_isletme_toplama": simdi}}
        )
        return await ctx.send("⏳ Sistem başlatıldı.")

    saat = int((simdi - son) // 3600)

    if saat <= 0:
        return await ctx.send("⏳ Henüz gelir oluşmadı.")

    if saat > 26:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"son_isletme_toplama": simdi}}
        )
        return await ctx.send("🔥 Geliri zamanında çekmedin. Hepsi yandı.")

    saat = min(saat, 24)

    toplam = 0

    for isim, veri in user.get("isletmeler", {}).items():

        adet = int(veri.get("adet", 0))
        level = int(veri.get("level", 1))

        if isim not in ISLETMELER:
            continue

        base = int(ISLETMELER[isim]["gelir"])

        gelir = base * adet * saat * (1 + (level - 1) * 0.10)
        toplam += int(gelir)

    if toplam <= 0:
        return await ctx.send("❌ İşletmen yok.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": int(toplam)},
            "$set": {"son_isletme_toplama": simdi}
        }
    )

    await ctx.send(
        f"🏭 Gelir toplandı\n"
        f"🕒 Süre: {saat} saat\n"
        f"💰 Kazanç: {formatla(int(toplam))}"
    )

# EVLENME

@bot.command(name="evlen")
@commands.cooldown(1, 5, commands.BucketType.user)
async def evlen(ctx, member: discord.Member):

    if member.id == ctx.author.id:
        return await ctx.send("❌ Kendinle evlenemezsin.")

    user = get_user(ctx.author.id)
    hedef = get_user(member.id)

    if user.get("married_to"):
        return await ctx.send("❌ Zaten evlisin.")

    if hedef.get("married_to"):
        return await ctx.send("❌ O kişi zaten evli.")

    if user.get("envanter", {}).get("Yüzük", 0) < 1:
        return await ctx.send("❌ Evlenmek için envanterinde Yüzük olmalı.")

    await ctx.send(
        f"💍 {member.mention}, {ctx.author.mention} sana evlilik teklifi etti.\n"
        "Kabul ediyorsan **evet** yaz.\n"
        "Reddediyorsan **hayır** yaz."
    )

    def check(m):
        return m.author.id == member.id and m.channel == ctx.channel and m.content.lower() in ["evet", "hayır"]

    try:
        msg = await bot.wait_for("message", timeout=60, check=check)
    except asyncio.TimeoutError:
        return await ctx.send("⏰ Süre doldu. Teklif iptal edildi.")

    if msg.content.lower() == "evet":

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {"envanter.Yüzük": -1},
                "$set": {"married_to": member.id}
            }
        )

        collection.update_one(
            {"_id": str(member.id)},
            {"$set": {"married_to": ctx.author.id}}
        )

        # 🔥 ROZET KONTROL
        await rozet_kontrol(ctx.author.id)
        await rozet_kontrol(member.id)

        await ctx.send("🎉 Tebrikler! Artık evlisiniz!")
    else:
        await ctx.send("❌ Evlilik teklifi reddedildi.")

# BOŞAN
@bot.command(name="boşan")
@commands.cooldown(1, 5, commands.BucketType.user)
async def bosan(ctx):

    user = get_user(ctx.author.id)

    if not user:
        return await ctx.send("❌ Kullanıcı verisi bulunamadı.")

    es_id = user.get("married_to")

    if not es_id:
        return await ctx.send("❌ Evli değilsin.")

    es_user = get_user(es_id)

    toplam_servet = user.get("para", 0) + user.get("banka", 0)
    tazminat = int(toplam_servet * 0.05)

    if user.get("para", 0) < tazminat:
        return await ctx.send(f"❌ Boşanmak için {formatla(tazminat)} EwoCoin gerekiyor.")

    # 💔 Boşanan kişi
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": -tazminat,
                "bosanma_sayisi": 1
            },
            "$set": {"married_to": None}
        }
    )

    # 💰 Eş
    collection.update_one(
        {"_id": str(es_id)},
        {
            "$inc": {"para": tazminat},
            "$set": {"married_to": None}
        }
    )

    # 🔥 Rozet kontrol
    await rozet_kontrol(ctx.author.id)

    await ctx.send(
        f"💔 {ctx.author.mention} boşandı.\n"
        f"💸 {formatla(tazminat)} EwoCoin tazminat ödendi."
    )

# GÖREV AL
@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def göreval(ctx):

    user = get_user(ctx.author.id)

    if user.get("aktif_gorev"):
        return await ctx.send("❌ Zaten aktif görevin var.")

    gorev_listesi = GOREVLER.copy()

    # işletme yoksa işletme görevini çıkar
    if not user.get("isletmeler"):
        gorev_listesi = [g for g in gorev_listesi if g["tip"] != "isletme"]

    secilen = random.choice(gorev_listesi)

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$set": {
                "aktif_gorev": secilen,
                "gorev_progress": 0
            }
        }
    )

    await ctx.send(
        f"🎯 Yeni Görev:\n"
        f"{secilen['ad']}\n"
        f"Hedef: {secilen['hedef']}\n"
        f"Ödül: {secilen['xp']} XP"
    )

# AKTİF GÖREV GÖR
@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def görevler(ctx):

    user = get_user(ctx.author.id)

    aktif = user.get("aktif_gorev")

    if not aktif:
        return await ctx.send("📭 Aktif görevin yok.")

    progress = user.get("gorev_progress", 0)

    await ctx.send(
        f"🎯 Aktif Görev: {aktif['ad']}\n"
        f"İlerleme: {progress} / {aktif['hedef']}\n"
        f"Ödül: {aktif['xp']} XP"
    )


# ROZETLERİM 
@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def rozetlerim(ctx):

    user = get_user(ctx.author.id)
    rozetler = user.get("rozetler", [])

    if not rozetler:
        return await ctx.send("🏅 Henüz rozetin yok.")

    text = "\n".join([f"🏅 {r}" for r in rozetler])

    embed = discord.Embed(
        title="🏅 Rozetlerin",
        description=text,
        color=discord.Color.orange()
    )

    await ctx.send(embed=embed)

# AKTİF ROZET SEÇ
@bot.command(name="hesaprozetekle")
@commands.cooldown(1, 5, commands.BucketType.user)
async def hesaprozetekle(ctx, *, rozet_adi):

    user = get_user(ctx.author.id)

    if rozet_adi not in user.get("rozetler", []):
        return await ctx.send("❌ Böyle bir rozete sahip değilsin.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$set": {"aktif_rozet": rozet_adi}}
    )

    await ctx.send(f"👑 Aktif rozet ayarlandı: {rozet_adi}")

@bot.command(name="rozetler")
@commands.cooldown(1, 5, commands.BucketType.user)
async def rozetler(ctx):

    user = get_user(ctx.author.id)
    sahip = user.get("rozetler", [])

    embed = discord.Embed(
        title="🏅 EwoBot Rozet Sistemi",
        description="Aşağıda bottaki tüm rozetler ve kazanma şartları yer alıyor.",
        color=discord.Color.orange()
    )

    rozet_text = ""

    for rozet, aciklama in ROZETLER.items():

        if rozet in sahip:
            rozet_text += f"✅ **{rozet}**\n┗ 📌 {aciklama}\n\n"
        else:
            rozet_text += f"❌ {rozet}\n┗ 📌 {aciklama}\n\n"

    # Discord 4096 karakter limiti için güvenlik
    if len(rozet_text) > 4000:
        rozet_text = rozet_text[:4000]

    embed.description += "\n\n" + rozet_text
    embed.set_footer(text=f"{len(sahip)} / {len(ROZETLER)} rozet kazanmışsın")

    await ctx.send(embed=embed)

def get_rank_name(point):
    if point >= 2000:
        return "👑 Efsanevi"
    elif point >= 1000:
        return "💎 Elmas"
    elif point >= 500:
        return "🥇 Altın"
    elif point >= 200:
        return "🥈 Gümüş"
    else:
        return "🥉 Bronz"


@bot.command()
@commands.cooldown(1, DUEL_COOLDOWN, commands.BucketType.user)
async def düello(ctx, member: discord.Member, bahis: int):

    if member.bot or member.id == ctx.author.id:
        return await ctx.send("❌ Geçersiz hedef.")

    if bahis < MINN_BET:
        return await ctx.send(f"❌ Minimum bahis {MINN_BET}")

    user1 = get_user(ctx.author.id)
    user2 = get_user(member.id)

    if user1["para"] < bahis or user2["para"] < bahis:
        return await ctx.send("❌ Yetersiz bakiye.")

    view = DuelAcceptView(ctx.author, member, bahis)

    embed = discord.Embed(
        title="⚔️ Düello Teklifi",
        description=f"{member.mention}, kabul ediyor musun?\nBahis: {bahis}",
        color=discord.Color.red()
    )

    await ctx.send(embed=embed, view=view)

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def rank(ctx):
    user = get_user(ctx.author.id)
    pvp = user.get("pvp", {})
    point = pvp.get("rank_point", 0)

    embed = discord.Embed(title="⚔️ PvP Rank", color=discord.Color.blurple())
    embed.add_field(name="Rank", value=get_rank_name(point))
    embed.add_field(name="Puan", value=point)
    embed.add_field(name="Win", value=pvp.get("win", 0))
    embed.add_field(name="Lose", value=pvp.get("lose", 0))

    await ctx.send(embed=embed)

class DuelView(discord.ui.View):
    def __init__(self, duel_id):
        super().__init__(timeout=None)
        self.duel_id = duel_id

    async def interaction_check(self, interaction: discord.Interaction):
        duel = active_duels.get(self.duel_id)
        if not duel:
            await interaction.response.send_message("Düello bitmiş.", ephemeral=True)
            return False

        if interaction.user.id != duel["turn"]:
            await interaction.response.send_message("Sıra sende değil.", ephemeral=True)
            return False

        return True

    async def process_turn(self, interaction, action):

        duel = active_duels[self.duel_id]

        attacker = duel["turn"]
        defender = duel["p1"] if attacker == duel["p2"] else duel["p2"]

        damage = 0
        heal = 0

        if action == "vur":
            damage = random.randint(50, 200)

            if duel["defending"] == defender:
                damage = int(damage * 0.5)

            duel["hp"][defender] -= damage
            text = f"💥 {interaction.user.display_name} {damage} hasar vurdu!"

        elif action == "savun":
            duel["defending"] = attacker
            text = f"🛡 {interaction.user.display_name} savunmaya geçti!"

        elif action == "can":
            heal = random.randint(50, 150)
            duel["hp"][attacker] += heal
            duel["hp"][attacker] = min(duel["hp"][attacker], 1000)
            text = f"❤️ {interaction.user.display_name} {heal} can yeniledi!"

        duel["turn"] = defender
        duel["last_action"] = time.time()

        # Kazanma kontrol
        if duel["hp"][defender] <= 0:
            await finish_duel(self.duel_id, attacker, defender, interaction.channel)
            self.stop()
            return

        attacker_member = interaction.guild.get_member(attacker)
        defender_member = interaction.guild.get_member(defender)

        embed = discord.Embed(title="⚔️ Düello Devam Ediyor", color=discord.Color.red())
        embed.description = (
            f"{attacker_member.display_name} ❤️ {duel['hp'][attacker]}\n"
            f"{defender_member.display_name} ❤️ {duel['hp'][defender]}\n\n"
            f"{text}\n\n🎯 Sıra: {defender_member.display_name}"
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="VUR", style=discord.ButtonStyle.danger)
    async def vur(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "vur")

    @discord.ui.button(label="SAVUN", style=discord.ButtonStyle.primary)
    async def savun(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "savun")

    @discord.ui.button(label="CAN", style=discord.ButtonStyle.success)
    async def can(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "can")


class DuelAcceptView(discord.ui.View):
    def __init__(self, p1, p2, bet):
        super().__init__(timeout=60)
        self.p1 = p1
        self.p2 = p2
        self.bet = bet

    @discord.ui.button(label="KABUL ET", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.p2:
            return await interaction.response.send_message("Bu teklif sana değil.", ephemeral=True)

        duel_id = f"{self.p1.id}-{self.p2.id}"

        active_duels[duel_id] = {
            "p1": self.p1.id,
            "p2": self.p2.id,
            "hp": {self.p1.id: 1000, self.p2.id: 1000},
            "turn": self.p1.id,
            "bet": self.bet,
            "defending": None,
            "last_action": time.time(),
            "channel_id": interaction.channel.id
        }

        collection.update_one({"_id": str(self.p1.id)}, {"$inc": {"para": -self.bet}})
        collection.update_one({"_id": str(self.p2.id)}, {"$inc": {"para": -self.bet}})

        embed = discord.Embed(title="⚔️ Düello Başladı!", color=discord.Color.dark_red())
        embed.description = f"{self.p1.display_name} vs {self.p2.display_name}\n\n🎯 Sıra: {self.p1.display_name}"

        view = DuelView(duel_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="REDDET", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.p2:
            return
        await interaction.response.edit_message(content="❌ Düello reddedildi.", embed=None, view=None)

async def on_timeout(self):
    for item in self.children:
        item.disabled = True

async def finish_duel(duel_id, winner, loser, channel):

    if duel_id not in active_duels:
        return

    duel = active_duels[duel_id]
    bet = duel["bet"]

    duel_history.setdefault(winner, [])
    history = duel_history[winner]

    anti_boost = loser in history[-5:]

    total = bet * 2

    winner_data = get_user(winner)
    duel_count = winner_data.get("pvp", {}).get("duel_count", 0)

    boost = 0
    if duel_count % 5 == 4:
        boost = int(total * 0.25)

    total += boost

    if not anti_boost:

        collection.update_one({"_id": str(winner)}, {
            "$inc": {
                "para": total,
                "pvp.win": 1,
                "pvp.rank_point": 25,
                "pvp.duel_count": 1
            }
        })

        loser_data = get_user(loser)
        current_point = loser_data.get("pvp", {}).get("rank_point", 0)
        new_point = max(0, current_point - 15)

        collection.update_one({"_id": str(loser)}, {
            "$inc": {
                "pvp.lose": 1,
                "pvp.duel_count": 1
            },
            "$set": {
                "pvp.rank_point": new_point
            }
        })

    duel_history[winner].append(loser)

    embed = discord.Embed(title="🏆 Düello Bitti!", color=discord.Color.gold())
    embed.description = f"<@{winner}> kazandı!\n💰 Ödül: {total}"

    if anti_boost:
        embed.add_field(name="⚠ Anti Boost", value="Rank puanı verilmedi.")

    await channel.send(embed=embed)

    del active_duels[duel_id]

@bot.command()
@commands.cooldown(1, 30, commands.BucketType.user)
async def gdüellocular(ctx):

    top = collection.find().sort("pvp.win", -1).limit(10)

    text = ""
    sıra = 1

    for user in top:
        win = user.get("pvp", {}).get("win", 0)
        if win <= 0:
            continue

        try:
            u = await bot.fetch_user(int(user["_id"]))
            isim = u.name
        except:
            isim = f"ID: {user['_id']}"

        text += f"**{sıra}.** {isim} — {win} win\n"
        sıra += 1

    if text == "":
        text = "Henüz global düello verisi yok."

    embed = discord.Embed(
        title="🌍 Global Düellocular",
        description=text,
        color=discord.Color.purple()
    )

    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def sdüellocular(ctx):

    guild_member_ids = [str(member.id) for member in ctx.guild.members]

    top = collection.find(
        {"_id": {"$in": guild_member_ids}}
    ).sort("pvp.win", -1).limit(10)

    text = ""
    sıra = 1

    for user in top:   # async for değil NORMAL for
        win = user.get("pvp", {}).get("win", 0)
        if win <= 0:
            continue

        member = ctx.guild.get_member(int(user["_id"]))

        if member:
            isim = member.display_name
        else:
            isim = f"ID: {user['_id']}"

        text += f"**{sıra}.** {isim} — {win} win\n"
        sıra += 1

    if text == "":
        text = "Bu sunucuda henüz düello kazanan yok."

    embed = discord.Embed(
        title=f"⚔️ {ctx.guild.name} Düello Sıralaması",
        description=text,
        color=discord.Color.gold()
    )

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    embed.set_footer(text="EwoBot PvP Sistemi")

    await ctx.send(embed=embed)

# Admin Prefix Ayarlama
@bot.command()
@commands.has_permissions(administrator=True)
async def prefix(ctx, yeni_prefix=None):

    if not ctx.guild:
        return await ctx.send("Bu komut sadece sunucularda kullanılabilir.")

    if not yeni_prefix:
        data = settings_collection.find_one({"_id": f"guild_{ctx.guild.id}"})
        mevcut = data.get("prefix") if data and "prefix" in data else "Varsayılan (q!)"
        return await ctx.send(f"📌 Mevcut prefix: `{mevcut}`")

    if len(yeni_prefix) > 5:
        return await ctx.send("❌ Prefix en fazla 5 karakter olabilir.")

    settings_collection.update_one(
        {"_id": f"guild_{ctx.guild.id}"},
        {"$set": {"prefix": yeni_prefix}},
        upsert=True
    )

    await ctx.send(f"✅ Prefix başarıyla `{yeni_prefix}` olarak ayarlandı.")

@bot.command()
@commands.has_permissions(administrator=True)
async def prefixsifirla(ctx):

    if not ctx.guild:
        return

    settings_collection.update_one(
        {"_id": f"guild_{ctx.guild.id}"},
        {"$unset": {"prefix": ""}}
    )

    await ctx.send("♻️ Prefix varsayılana döndü (q!)")

BOT_OWNER_ID = 1271933410251772017

@bot.check
async def global_kanal_kontrol(ctx):

    # Owner bypass
    if ctx.author.id == BOT_OWNER_ID:
        return True

    # DM serbest
    if not ctx.guild:
        return True

    # Kanal kilitliyse sadece komutaç çalışsın
    if await kanal_kilitli_mi(ctx.guild.id, ctx.channel.id):
        if ctx.command.name == "komutaç":
            return True
        return False

    return True

@bot.command()
@commands.has_permissions(administrator=True)
async def komutkapat(ctx):

    if not ctx.guild:
        return await ctx.send("Bu komut sadece sunucularda kullanılabilir.")

    settings_collection.update_one(
        {"_id": f"guild_{ctx.guild.id}"},
        {"$addToSet": {"disabled_channels": ctx.channel.id}},
        upsert=True
    )

    await ctx.send("🔒 Bu kanalda bot komutları kapatıldı.")

@bot.command()
@commands.has_permissions(administrator=True)
async def komutaç(ctx):

    if not ctx.guild:
        return await ctx.send("Bu komut sadece sunucularda kullanılabilir.")

    settings_collection.update_one(
        {"_id": f"guild_{ctx.guild.id}"},
        {"$pull": {"disabled_channels": ctx.channel.id}}
    )

    await ctx.send("🔓 Bu kanalda bot komutları tekrar açıldı.")

@tasks.loop(hours=1)
async def vergi_sistemi():

    simdi = int(time.time())
    users = collection.find()

    for user in users:

        son_vergi = user.get("son_vergi_zamani", 0)

        if simdi - son_vergi < 86400:
            continue

        nakit = int(user.get("para", 0))
        banka = int(user.get("banka", 0))
        isletmeler = user.get("isletmeler", {})

        isletme_degeri = 0

        for isim, data in isletmeler.items():

            adet = int(data.get("adet", 0))

            if isim in ISLETMELER:
                fiyat = ISLETMELER[isim]["fiyat"]
            else:
                fiyat = 0

            isletme_degeri += fiyat * adet

        servet = nakit + banka + isletme_degeri

        if servet < 2500000:
            continue

        # ⭐ Premium kontrol
        if is_premium(user):
            vergi_orani = 0.01
            premium_mesaj = "\n⭐ Premium olduğunuz için vergi oranı %1 uygulandı."
        else:
            vergi_orani = 0.02
            premium_mesaj = ""

        vergi = int(servet * vergi_orani)

        kesilen = 0
        yeni_isletmeler = isletmeler.copy()

        # 1️⃣ Nakitten kes
        if nakit >= vergi:

            kesilen = vergi

            collection.update_one(
                {"_id": user["_id"]},
                {
                    "$inc": {"para": -vergi},
                    "$set": {"son_vergi_zamani": simdi}
                }
            )

        else:

            toplam_para = nakit + banka

            # 2️⃣ Bankadan kes
            if toplam_para >= vergi:

                kalan = vergi - nakit
                kesilen = vergi

                collection.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "para": 0,
                            "son_vergi_zamani": simdi
                        },
                        "$inc": {"banka": -kalan}
                    }
                )

            else:

                # 3️⃣ İşletme sil
                eksik = vergi - toplam_para
                kesilen = vergi

                for isim in list(yeni_isletmeler.keys()):

                    adet = yeni_isletmeler[isim].get("adet", 0)

                    if isim not in ISLETMELER:
                        continue

                    fiyat = ISLETMELER[isim]["fiyat"]

                    while adet > 0 and eksik > 0:

                        adet -= 1
                        eksik -= fiyat

                    if adet <= 0:
                        del yeni_isletmeler[isim]
                    else:
                        yeni_isletmeler[isim]["adet"] = adet

                    if eksik <= 0:
                        break

                collection.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "para": 0,
                            "banka": 0,
                            "isletmeler": yeni_isletmeler,
                            "son_vergi_zamani": simdi
                        }
                    }
                )

        # 📩 DM gönder
        try:

            kullanici = await bot.fetch_user(int(user["_id"]))

            await kullanici.send(
                f"🏦 **EwoBot Vergi Sistemi**\n\n"
                f"💰 Kesilen Vergi: {formatla(kesilen)}\n"
                f"📊 Toplam Servet: {formatla(servet)}\n"
                f"📉 Vergi Oranı: %{int(vergi_orani*100)}"
                f"{premium_mesaj}\n\n"
                f"⚠️ Vergi otomatik olarak kesildi."
            )

        except:
            pass

@bot.command()
@commands.cooldown(1, 750, commands.BucketType.user)
async def baskın(ctx, member: discord.Member, *, isletme: str):

    if member.bot or member == ctx.author:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Geçersiz hedef.")

    user = get_user(ctx.author.id)
    hedef = get_user(member.id)

    isletme = isletme.lower()

    # özel araç kontrol
    if user["envanter"].get("Özel Araçgereçler", 0) <= 0:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Baskın için **Özel Araçgereçler** lazım!")

    # 200k para kontrol
    baskin_ucreti = 200000

    if user["para"] < baskin_ucreti:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Baskın yapmak için en az **200.000** paran olmalı!")

    # işletme kontrol
    hedef_isletmeler = hedef.get("isletmeler", {})

    if isletme not in hedef_isletmeler:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Bu kişinin böyle bir işletmesi yok!")

    # baskın ücreti düş
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -baskin_ucreti}}
    )

    basari = 0.45

    gelir = isletme_geliri_hesapla(hedef, isletme)

    if random.random() < basari:

        calinan = int(gelir * 0.40)

        hedef_para = hedef.get("para", 0)

        if calinan > hedef_para:
            calinan = hedef_para

        if calinan <= 0:
            return await ctx.send("❌ Hedefte çalacak para yok.")

        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"para": -calinan}}
        )

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": calinan}}
        )

        mesaj = (
            f"🚨 **Baskın Başarılı!**\n\n"
            f"🏭 Hedef: {isletme.capitalize()}\n"
            f"💰 Çalınan Para: **{formatla(calinan)}**"
        )

    else:

        ceza = 200000

        mesaj = (
            f"👮 **Polis seni yakaladı!**\n\n"
            f"💸 Ceza: **{formatla(ceza)}**"
        )

    # araç düş
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"envanter.Özel Araçgereçler": -1}}
    )

    await ctx.send(mesaj)

@bot.command(name="mafyakur")
@commands.cooldown(1, 7, commands.BucketType.user)
async def mafyakur(ctx, isim: str):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if user.get("mafia_id"):
        return await ctx.send("❌ Zaten bir mafyadasın.")

    if user.get("level", 0) < 5:
        return await ctx.send("❌ Mafya kurmak için **5 level** olmalısın.")

    if user.get("para", 0) < 1_000_000:
        return await ctx.send("❌ Mafya kurmak için **1.000.000** para gerekli.")

    if mafia_col.find_one({"name": isim}):
        return await ctx.send("❌ Bu isimde mafya var.")

    mafia_id = str(uuid.uuid4())

    mafia = {
        "_id": mafia_id,
        "name": isim,
        "leader": user_id,
        "members": [user_id],
        "capacity": 5,
        "bank": 0,
        "wins": 0,
        "guild": ctx.guild.id,
        "war": None,

        "roles": [
            {"name": "Mafya Lideri", "rank": 10, "manager": True},
            {"name": "Mafya Yöneticisi", "rank": 7, "manager": True},
            {"name": "Mafya Üyesi", "rank": 1, "manager": False}
        ],

        # 🌍 BÖLGE SİSTEMİ
        "regions": {},
        "last_region_collect": int(time.time())
    }

    mafia_col.insert_one(mafia)

    collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "mafia_id": mafia_id,
                "mafia_role": "leader",
                "mafia_custom_role": "Mafya Lideri"
            },
            "$inc": {
                "para": -1_000_000
            }
        }
    )

    embed = discord.Embed(
        title="🏴 Yeni Mafya Kuruldu!",
        description=f"**{isim}** mafyası {ctx.author.mention} tarafından kuruldu.",
        color=0x000000
    )

    await ctx.send(embed=embed)

# =========================
# MAFYA BİLGİ
# =========================

@bot.command(name="mafyabilgi")
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafya_bilgi(ctx):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    embed = discord.Embed(title=f"🏴 {mafia['name']}")

    embed.add_field(
        name="👑 Lider",
        value=f"<@{mafia['leader']}>"
    )

    embed.add_field(
        name="👥 Üye",
        value=f"{len(mafia['members'])}/{mafia['capacity']}"
    )

    embed.add_field(
        name="💰 Kasa",
        value=f"{mafia['bank']:,}"
    )

    embed.add_field(
        name="🏆 Savaş",
        value=mafia["wins"]
    )

    await ctx.send(embed=embed)

@bot.command(name="mafyaat")
async def mafyaat(ctx, member: discord.Member):

    if member.id == ctx.author.id:
        return await ctx.send("❌ Kendini atamazsın.")

    user = get_user(ctx.author.id)
    target = get_user(member.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    if user.get("mafia_id") != target.get("mafia_id"):
        return await ctx.send("❌ Aynı mafyada değilsiniz.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if target.get("mafia_role") == "leader":
        return await ctx.send("❌ Lideri atamazsın.")

    roles = mafia["roles"]

    giver_role = next(
        (r for r in roles if r["name"] == user.get("mafia_custom_role")),
        None
    )

    target_role = next(
        (r for r in roles if r["name"] == target.get("mafia_custom_role")),
        None
    )

    # Lider herkesi atabilir
    if user.get("mafia_role") != "leader":

        if not giver_role or not giver_role["manager"]:
            return await ctx.send("❌ Üye atma yetkin yok.")

        if not target_role:
            return await ctx.send("❌ Hedef rol bulunamadı.")

        if giver_role["rank"] <= target_role["rank"]:
            return await ctx.send("❌ Kendinden yüksek veya eşit rolü atamazsın.")

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {"$pull": {"members": str(member.id)}}
    )

    collection.update_one(
        {"_id": str(member.id)},
        {
            "$set": {
                "mafia_id": None,
                "mafia_role": None,
                "mafia_custom_role": "Mafya Üyesi"
            }
        }
    )

    await ctx.send(f"🚫 {member.mention} mafyadan atıldı.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafyadavet(ctx, member: discord.Member):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Bir mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if not mafia:
        return await ctx.send("❌ Mafya bulunamadı.")

    # davet edilen kişi zaten mafyada mı
    target = get_user(member.id)

    if target.get("mafia_id"):
        return await ctx.send("❌ Bu kullanıcı zaten bir mafyada.")

    # rol listesi
    roles = mafia["roles"]

    user_role = next(
        (r for r in roles if r["name"] == user.get("mafia_custom_role")),
        None
    )

    # yetki kontrolü
    if user.get("mafia_role") != "leader":
        if not user_role or not user_role.get("manager"):
            return await ctx.send("❌ Davet etme yetkin yok.")

    # kapasite kontrol
    if len(mafia["members"]) >= mafia["capacity"]:
        return await ctx.send("❌ Mafya dolu.")

    mafia_invites.update_one(
        {"user": str(member.id)},
        {"$addToSet": {"invites": mafia["_id"]}},
        upsert=True
    )

    await ctx.send(f"📨 {member.mention} mafyaya davet edildi.")

# =========================
# MAFYA KABUL
# =========================

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafyakabul(ctx):

    user_id = str(ctx.author.id)

    data = mafia_invites.find_one({"user": user_id})

    if not data or not data.get("invites"):
        return await ctx.send("❌ Davetin yok.")

    mafia_id = data["invites"][0]

    mafia = mafia_col.find_one({"_id": mafia_id})

    if not mafia:
        return await ctx.send("❌ Mafya bulunamadı.")

    if len(mafia["members"]) >= mafia["capacity"]:
        return await ctx.send("❌ Mafya dolu.")

    mafia_col.update_one(
        {"_id": mafia_id},
        {"$push": {"members": user_id}}
    )

    collection.update_one(
        {"_id": user_id},
        {"$set": {"mafia_id": mafia_id, "mafia_role": "member"}}
    )

    mafia_invites.delete_one({"user": user_id})

    await ctx.send(f"✅ {mafia['name']} mafyasına katıldın.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafyaayrıl(ctx):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {"$pull": {"members": user_id}}
    )

    # lider ayrılırsa
    if mafia["leader"] == user_id:

        members = mafia["members"]
        members.remove(user_id)

        if len(members) == 0:
            mafia_col.delete_one({"_id": mafia["_id"]})
            await ctx.send("🏴 Mafya dağıldı.")
        else:
            new_leader = random.choice(members)

            mafia_col.update_one(
                {"_id": mafia["_id"]},
                {"$set": {"leader": new_leader}}
            )

            collection.update_one(
                {"_id": new_leader},
                {"$set": {"mafia_role": "leader"}}
            )

            await ctx.send(f"👑 Yeni lider <@{new_leader}> oldu.")

    collection.update_one(
        {"_id": user_id},
        {"$set": {"mafia_id": None, "mafia_role": None}}
    )

    await ctx.send("🚪 Mafyadan ayrıldın.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafyayatır(ctx, miktar: int):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yok.")

    mafia_col.update_one(
        {"_id": user["mafia_id"]},
        {"$inc": {"bank": miktar}}
    )

    collection.update_one(
        {"_id": user_id},
        {"$inc": {"para": -miktar}}
    )

    await ctx.send(f"💰 Mafya kasasına {miktar:,} yatırıldı.")

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def mafyacek(ctx, miktar: int):

    user_id = str(ctx.author.id)
    user = get_user(user_id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider çekebilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if mafia["bank"] < miktar:
        return await ctx.send("❌ Kasada yeterli para yok.")

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {"$inc": {"bank": -miktar}}
    )

    collection.update_one(
        {"_id": user_id},
        {"$inc": {"para": miktar}}
    )

    await ctx.send(f"💰 Kasadan {miktar:,} çekildi.")

# =========================
# MAFYA GÜÇ
# =========================

def mafia_power(mafia):

    total = 0

    for m in mafia["members"]:
        u = get_user(m)
        total += u.get("money_earned",0)

    return total


# =========================
# MAFYA BASKIN
# =========================

@bot.command()
@commands.cooldown(1, 450, commands.BucketType.user)
async def mafyabaskın(ctx, isim):

    user = get_user(ctx.author.id)

    if not user.get("mafia_id"):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Bir mafyada değilsin.")

    attacker = mafia_col.find_one({"_id": user["mafia_id"]})

    defender = mafia_col.find_one({
        "name": {"$regex": f"^{re.escape(isim)}$", "$options": "i"}
    })

    if not defender:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Mafya bulunamadı.")

    if attacker["_id"] == defender["_id"]:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Kendi mafyana saldıramazsın.")

    # saldıran kasa kontrol
    if attacker.get("bank", 0) < 25000:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Baskın atmak için mafya kasasında en az **25.000 Ewocoin** olmalı.")

    # savunan kasa kontrol
    defender_bank = defender.get("bank", 0)

    if defender_bank < 30000:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Baskın atılan mafyanın kasasında en az **30.000 Ewocoin** olmalı.")

    # saldırı ihtimali
    chance = random.randint(1, 100)

    embed = discord.Embed(title="💣 MAFYA BASKINI")

    embed.add_field(name="Saldıran Mafya", value=attacker["name"])
    embed.add_field(name="Savunma Mafyası", value=defender["name"])

    # =================
    # BAŞARILI BASKIN (%40)
    # =================
    if chance <= 40:

        max_steal = int(defender_bank * 0.25)
        stolen = random.randint(int(max_steal * 0.5), max_steal)

        mafia_col.update_one(
            {"_id": defender["_id"]},
            {"$inc": {"bank": -stolen}}
        )

        mafia_col.update_one(
            {"_id": attacker["_id"]},
            {"$inc": {"bank": stolen}}
        )

        embed.color = 0x00ff00
        embed.add_field(
            name="⚔️ Sonuç",
            value="Saldırı başarılı oldu!"
        )

        embed.add_field(
            name="💰 Çalınan Para",
            value=f"{stolen:,} Ewocoin",
            inline=False
        )

    # =================
    # SAVUNMA (%60)
    # =================
    else:

        attacker_bank = attacker.get("bank", 0)

        penalty = int(attacker_bank * 0.10)

        mafia_col.update_one(
            {"_id": attacker["_id"]},
            {"$inc": {"bank": -penalty}}
        )

        mafia_col.update_one(
            {"_id": defender["_id"]},
            {"$inc": {"bank": penalty}}
        )

        embed.color = 0xff0000
        embed.add_field(
            name="🛡️ Sonuç",
            value="Savunan mafya saldırıyı **bertaraf etti!**"
        )

        embed.add_field(
            name="💸 Ceza",
            value=f"Saldıran mafyanın kasasından **{penalty:,} Ewocoin** alındı.",
            inline=False
        )

    await ctx.send(embed=embed)

# =========================
# SUNUCU MAFYALARI
# =========================

@bot.command()
@commands.cooldown(1, 20, commands.BucketType.user)
async def smafyalar(ctx):

    mafias = mafia_col.find({"guild": ctx.guild.id}).sort("bank",-1).limit(10)

    embed = discord.Embed(title="🏆 En Güçlü Mafyalar")

    for i, m in enumerate(mafias, 1):

        uye = len(m["members"])
        kasa = m.get("bank",0)

        embed.add_field(
            name=f"{i}. {m['name']}",
            value=f"👥 Üye: {uye}\n💰 Kasa: {kasa:,}",
            inline=False
        )

    await ctx.send(embed=embed)

# =========================
# GLOBAL MAFYA
# =========================

@bot.command()
@commands.cooldown(1, 20, commands.BucketType.user)
async def gmafyalar(ctx):

    mafias = mafia_col.find().sort("bank",-1).limit(10)

    embed = discord.Embed(title="🌍 En Güçlü Mafyalar")

    for i, m in enumerate(mafias,1):

        uye = len(m["members"])
        kasa = m.get("bank",0)

        embed.add_field(
            name=f"{i}. {m['name']}",
            value=f"👥 Üye: {uye}\n💰 Kasa: {kasa:,}",
            inline=False
        )

    await ctx.send(embed=embed)

# =========================
# GLOBAL BOARD
# =========================

@tasks.loop(hours=2)
async def mafia_board():

    global mafia_msg

    guild = bot.get_guild(1471843922115301493)
    if not guild:
        return

    channel = guild.get_channel(1479642291663802569)
    if not channel:
        return

    mafias = mafia_col.find().sort("bank",-1).limit(10)

    embed = discord.Embed(
        title="🌍 En Güçlü Mafyalar",
        color=0x000000
    )

    for i, mafia in enumerate(mafias, 1):

        uye = len(mafia["members"])
        kasa = mafia.get("bank",0)

        embed.add_field(
            name=f"{i}. {mafia['name']}",
            value=f"👥 Üye: {uye}\n💰 Kasa: {kasa:,}",
            inline=False
        )

    if mafia_msg:
        await mafia_msg.edit(embed=embed)
    else:
        mafia_msg = await channel.send(embed=embed)

@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def mafyam(ctx):

    user = get_user(ctx.author.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Bir mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if not mafia:
        return await ctx.send("❌ Mafya bulunamadı.")

    embed = discord.Embed(
        title=f"🏴 {mafia['name']}",
        color=0x2f3136
    )

    embed.add_field(
        name="👑 Lider",
        value=f"<@{mafia['leader']}>",
        inline=False
    )

    embed.add_field(
        name="👥 Üye",
        value=f"{len(mafia['members'])}/{mafia['capacity']}",
        inline=True
    )

    embed.add_field(
        name="💰 Kasa",
        value=f"{mafia.get('bank',0):,}",
        inline=True
    )

    view = None

    # sadece lider butonu görür
    if str(ctx.author.id) == str(mafia["leader"]):
        view = MafiaUpgradeView()

    await ctx.send(embed=embed, view=view)

class MafiaUpgradeView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⬆ Mafya Grubunu Yükselt", style=discord.ButtonStyle.green)
    async def upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = get_user(interaction.user.id)

        if not user.get("mafia_id"):
            return await interaction.response.send_message("❌ Mafyada değilsin.", ephemeral=True)

        mafia = mafia_col.find_one({"_id": user["mafia_id"]})

        if not mafia:
            return await interaction.response.send_message("❌ Mafya bulunamadı.", ephemeral=True)

        # sadece lider yükseltebilir
        if str(interaction.user.id) != str(mafia["leader"]):
            return await interaction.response.send_message(
                "❌ Sadece mafya lideri yükseltebilir.",
                ephemeral=True
            )

        levels = [
            (5, 7, 500000),
            (7, 10, 1000000),
            (10, 15, 2000000),
            (15, 20, 5000000)
        ]

        current_capacity = mafia["capacity"]

        for old, new, price in levels:

            if current_capacity == old:

                if mafia.get("bank",0) < price:
                    return await interaction.response.send_message(
                        f"❌ Mafya kasasında **{price:,}** para olmalı.",
                        ephemeral=True
                    )

                mafia_col.update_one(
                    {"_id": mafia["_id"]},
                    {
                        "$inc": {"bank": -price},
                        "$set": {"capacity": new}
                    }
                )

                return await interaction.response.send_message(
                    f"🎉 Mafya kapasitesi **{new} kişi** oldu!\n💰 **{price:,}** kasa parası kullanıldı."
                )

        await interaction.response.send_message(
            "❌ Mafya zaten maksimum seviyede.",
            ephemeral=True
        )

@bot.command()
@commands.cooldown(1, 2, commands.BucketType.user)
async def mafyasil(ctx, *, isim):

    if ctx.author.id != 1271933410251772017:
        return await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir.")

    mafia = mafia_col.find_one({"name": isim})

    if not mafia:
        return await ctx.send("❌ Mafya bulunamadı.")

    # üyelerin mafyasını sıfırla
    for m in mafia["members"]:
        collection.update_one(
            {"_id": str(m)},
            {
                "$set": {
                    "mafia_id": None,
                    "mafia_role": None
                }
            }
        )

    mafia_col.delete_one({"_id": mafia["_id"]})

    await ctx.send(f"🗑 **{isim}** mafyası silindi.")

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def mafyadevret(ctx, member: discord.Member):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider devredebilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if str(member.id) not in mafia["members"]:
        return await ctx.send("❌ Kullanıcı mafyada değil.")

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {"$set": {"leader": str(member.id)}}
    )

    collection.update_one(
        {"_id": str(member.id)},
        {"$set": {"mafia_role": "leader"}}
    )

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$set": {"mafia_role": "member"}}
    )

    await ctx.send(f"👑 Liderlik {member.mention} kullanıcısına devredildi.")

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def mafyarolleri(ctx):

    user = get_user(ctx.author.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    roles = sorted(mafia["roles"], key=lambda x: x["rank"], reverse=True)

    embed = discord.Embed(
        title=f"🏴 {mafia['name']} Mafya Rolleri",
        color=0x2f3136
    )

    for r in roles:

        yonetici = "✅" if r["manager"] else "❌"

        embed.add_field(
            name=r["name"],
            value=f"Rank: {r['rank']}\nYönetici Yetkisi: {yonetici}",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name="rololustur")
@commands.cooldown(1, 7, commands.BucketType.user)
async def rololustur(ctx, *, args):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider rol oluşturabilir.")

    try:
        rol, rank = args.rsplit(" ", 1)
        rank = int(rank)
    except:
        return await ctx.send("❌ Kullanım: qrololustur <rolismi> <rank>")

    if rank < 1 or rank > 10:
        return await ctx.send("❌ Rank **1 ile 10 arasında** olmalı.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if len(mafia["roles"]) >= 10:
        return await ctx.send("❌ En fazla **10 rol** olabilir.")

    for r in mafia["roles"]:

        if r["name"].lower() == rol.lower():
            return await ctx.send("❌ Bu isimde rol var.")

        if r["rank"] == rank:
            return await ctx.send("❌ Bu rank zaten kullanılıyor.")

    if mafia["bank"] < 25000:
        return await ctx.send("❌ Mafya kasasında **25.000** yok.")

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {
            "$push": {
                "roles": {
                    "name": rol,
                    "rank": rank,
                    "manager": False
                }
            },
            "$inc": {"bank": -25000}
        }
    )

    await ctx.send(f"✅ **{rol}** rolü oluşturuldu. (Rank: {rank})")

@bot.command(name="roldegistir")
@commands.cooldown(1, 7, commands.BucketType.user)
async def roldegistir(ctx, member: discord.Member, *, rol):

    if member.id == ctx.author.id:
        return await ctx.send("❌ Kendi rolünü değiştiremezsin.")

    user = get_user(ctx.author.id)
    target = get_user(member.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    if user.get("mafia_id") != target.get("mafia_id"):
        return await ctx.send("❌ Aynı mafyada değilsiniz.")

    if target.get("mafia_role") == "leader":
        return await ctx.send("❌ Liderin rolü değiştirilemez.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    roles = mafia["roles"]

    giver_role = next(
        (r for r in roles if r["name"] == user.get("mafia_custom_role")),
        None
    )

    target_role = next(
        (r for r in roles if r["name"].lower() == rol.lower()),
        None
    )

    if not target_role:
        return await ctx.send("❌ Rol bulunamadı.")

    if not giver_role and user.get("mafia_role") != "leader":
        return await ctx.send("❌ Rolün bulunamadı.")

    if not giver_role["manager"] and user.get("mafia_role") != "leader":
        return await ctx.send("❌ Rol değiştirme yetkin yok.")

    if giver_role and giver_role["rank"] <= target_role["rank"]:
        return await ctx.send("❌ Kendinden yüksek rol veremezsin.")

    collection.update_one(
        {"_id": str(member.id)},
        {"$set": {"mafia_custom_role": target_role["name"]}}
    )

    await ctx.send(
        f"✅ {member.mention} artık **{target_role['name']}** rolünde."
    )

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def yöneticiver(ctx, *, rol):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider kullanabilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    for r in mafia["roles"]:

        if r["name"].lower() == rol.lower():

            mafia_col.update_one(
                {"_id": mafia["_id"], "roles.name": r["name"]},
                {"$set": {"roles.$.manager": True}}
            )

            return await ctx.send(f"✅ **{r['name']}** rolüne yönetici yetkisi verildi.")

    await ctx.send("❌ Rol bulunamadı.")

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def yöneticikaldir(ctx, *, rol):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider kullanabilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    for r in mafia["roles"]:

        if r["name"].lower() == rol.lower():

            mafia_col.update_one(
                {"_id": mafia["_id"], "roles.name": r["name"]},
                {"$set": {"roles.$.manager": False}}
            )

            return await ctx.send(f"❌ **{rol}** yönetici yetkisi kaldırıldı.")

    await ctx.send("❌ Rol bulunamadı.")


@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def rolkaldir(ctx, *, rol):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider kullanabilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    if mafia["bank"] < 1000:
        return await ctx.send("❌ Mafya kasasında **1000** yok.")

    users = collection.find({"mafia_id": mafia["_id"], "mafia_custom_role": rol})

    if list(users):
        return await ctx.send("❌ Bu rolde kullanıcı var.")

    mafia_col.update_one(
        {"_id": mafia["_id"]},
        {
            "$pull": {"roles": {"name": rol}},
            "$inc": {"bank": -1000}
        }
    )

    await ctx.send(f"🗑 **{rol}** rolü silindi.")

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def mafyalistesi(ctx):

    user = get_user(ctx.author.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    users = collection.find({"mafia_id": mafia["_id"]})

    embed = discord.Embed(
        title=f"🏴 {mafia['name']} Üyeleri",
        color=0x2f3136
    )

    text = ""

    for u in users:

        member = ctx.guild.get_member(int(u["_id"]))

        if not member:
            continue

        rol = u.get("mafia_custom_role", "Mafya Üyesi")

        text += f"{member.mention} → **{rol}**\n"

    embed.description = text

    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def mafyarol(ctx):

    user = get_user(ctx.author.id)

    if not user.get("mafia_id"):
        return await ctx.send("❌ Mafyada değilsin.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    role_name = user.get("mafia_custom_role")

    role = next((r for r in mafia["roles"] if r["name"] == role_name), None)

    manager = "✅ Var" if role and role["manager"] else "❌ Yok"

    embed = discord.Embed(
        title="🏴 Mafya Rolün",
        color=0x2f3136
    )

    embed.add_field(name="Rol", value=role_name)
    embed.add_field(name="Yönetici Yetkisi", value=manager)

    await ctx.send(embed=embed)

@bot.command(name="rolisimdegistir")
@commands.cooldown(1, 7, commands.BucketType.user)
async def rolisimdegistir(ctx, eski_rol, *, yeni_rol):

    user = get_user(ctx.author.id)

    if user.get("mafia_role") != "leader":
        return await ctx.send("❌ Sadece lider rol isimlerini değiştirebilir.")

    mafia = mafia_col.find_one({"_id": user["mafia_id"]})

    for r in mafia["roles"]:

        if r["name"].lower() == eski_rol.lower():

            mafia_col.update_one(
                {"_id": mafia["_id"], "roles.name": r["name"]},
                {"$set": {"roles.$.name": yeni_rol}}
            )

            # kullanıcıların rolünü de güncelle
            collection.update_many(
                {"mafia_id": mafia["_id"], "mafia_custom_role": r["name"]},
                {"$set": {"mafia_custom_role": yeni_rol}}
            )

            return await ctx.send(f"✅ **{eski_rol}** rolünün adı **{yeni_rol}** olarak değiştirildi.")

    await ctx.send("❌ Rol bulunamadı.")

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def premiumver(ctx, member: discord.Member, gun: int):

    if ctx.author.id != BOT_OWNER_ID:
        return

    sure = int(time.time()) + (gun * 86400)

    collection.update_one(
        {"_id": str(member.id)},
        {
            "$set": {"premium_until": sure},
            "$addToSet": {"rozetler": "Premium Üye"}
        },
        upsert=True
    )

    await ctx.send(f"⭐ {member.mention} kullanıcısına **{gun} gün premium** verildi.")

@tasks.loop(minutes=30)
async def premium_kontrol():

    simdi = int(time.time())

    users = collection.find({
        "premium_until": {"$lt": simdi},
        "rozetler": {"$in": ["Premium Üye"]}
    })

    for user in users:

        collection.update_one(
            {"_id": user["_id"]},
            {"$pull": {"rozetler": "Premium Üye"}}
        )

        try:
            uye = await bot.fetch_user(int(user["_id"]))
            await uye.send("⭐ Premium süren bitti ve **Premium Üye rozeti** kaldırıldı.")
        except:
            pass

@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def premium(ctx):

    user = get_user(ctx.author.id)

    simdi = int(time.time())
    premium_until = user.get("premium_until", 0)

    if premium_until <= simdi:
        return await ctx.send("❌ Premium üyeliğin yok.")

    kalan = premium_until - simdi

    gun = kalan // 86400
    saat = (kalan % 86400) // 3600

    # premium istatistikleri
    toplam_gun = user.get("premium_total_days", 0)
    premium_sayisi = user.get("premium_count", 1)
    seri = user.get("premium_series", 1)

    baslangic = premium_until - (gun * 86400 + saat * 3600)

    embed = discord.Embed(
        title="⭐ Premium Üyelik Bilgileri",
        color=discord.Color.gold()
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    embed.add_field(
        name="⏳ Kalan Süre",
        value=f"**{gun} gün {saat} saat**",
        inline=False
    )

    embed.add_field(
        name="📅 Premium Bitiş",
        value=f"<t:{premium_until}:F>",
        inline=False
    )

    embed.add_field(
        name="📊 Premium İstatistikleri",
        value=(
            f"💎 Premium Sayısı: **{premium_sayisi}**\n"
            f"🔥 Premium Serisi: **{seri}. Ay**\n"
            f"📆 Toplam Premium Gün: **{toplam_gun} gün**"
        ),
        inline=False
    )

    embed.set_footer(text=f"{ctx.author.name} • Premium Kullanıcısı")

    await ctx.send(embed=embed)



# =====================================================
# DUEL TIMEOUT LOOP
# =====================================================

@tasks.loop(seconds=10)
async def duel_timeout_checker():
    now = time.time()

    for duel_id, duel in list(active_duels.items()):
        try:
            if now - duel["last_action"] > DUEL_TIMEOUT:

                loser = duel["turn"]
                winner = duel["p1"] if loser == duel["p2"] else duel["p2"]

                channel = bot.get_channel(duel["channel_id"])

                if channel:
                    await finish_duel(duel_id, winner, loser, channel)

        except Exception as e:
            print(f"Duel timeout hatası ({duel_id}): {e}")

@bot.command()
async def sezonreset(ctx):

    if ctx.author.id != 1271933410251772017:
        return await ctx.send("❌ Bu komutu sadece bot sahibi kullanabilir.")

    collection.update_many(
        {},
        {
            "$set": {
                "para": 2500,
                "banka": 500,
                "meslek": "İşsiz",
                "xp": 0,
                "level": 1,
                "son_maas": 0,
                "son_gunluk": 0,

                "cf_sayisi": 0,
                "slot_sayisi": 0,
                "blackjack_sayisi": 0,
                "toplam_kazanc": 0,
                "toplam_kayip": 0,
                "bosanma_sayisi": 0,

                "aktif_gorev": None,
                "gorev_progress": 0,
                "tamamlanan_gorev": 0,

                "rozetler": [],
                "aktif_rozet": None,

                "envanter": {
                    "Bronz Kasa": 0,
                    "Gümüş Kasa": 0,
                    "Altın Kasa": 0,
                    "Elmas Kasa": 0,
                    "Premium Kasa": 0,
                    "EwoPlus Kasa": 0,
                    "Silah": 0,
                    "Özel Koruma": 0,
                    "Olta": 0,
                    "Yüzük": 0
                },

                "yatirimlar": {
                    "Altın": 0,
                    "Plus": 0,
                    "Bitcoin": 0,
                    "Elmas": 0,
                    "Dolar": 0,
                    "Gümüş": 0
                },

                "isletmeler": {},

                "pvp": {
                    "win": 0,
                    "lose": 0,
                    "rank_point": 0,
                    "duel_count": 0,
                    "afk_penalty_until": 0,
                    "last_duel_users": {}
                },

                "mafia_id": None,
                "mafia_role": None,
                "mafia_invites": [],

                "money_earned": 0,

                "season_reward_claimed": False
            }
        }
    )

    mafia_col.delete_many({})

    await ctx.send("✅ **Yeni sezon başlatıldı! Tüm ekonomi sıfırlandı.**")


# Bot tamamen hazır olmadan loop başlamasın
@duel_timeout_checker.before_loop
async def before_duel_timeout_checker():
    await bot.wait_until_ready()

@bot.event
async def on_ready():

    if getattr(bot, "ready_once", False):
        return

    bot.ready_once = True

    print("===================================")
    print(f"{bot.user} aktif!")
    print(f"Sunucu sayısı: {len(bot.guilds)}")
    print("===================================")

    # Invite Cache
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = invites
        except Exception as e:
            print(f"Invite cache hatası ({guild.name}): {e}")

    # Persistent View
    try:
        bot.add_view(TicketPanelView())
        print("TicketPanelView yüklendi")
    except Exception as e:
        print("TicketPanelView yüklenemedi:", e)

# ÖNERİ SİSTEMİ VIEW

    try:
        bot.add_view(OneriView(None, None))
        print("OneriView yüklendi")
    except Exception as e:
        print("OneriView yüklenemedi:", e)

    # LOOPLAR
    loops = [
        duel_timeout_checker,
        durum_degistir,
        otomatik_gzenginler,
        enflasyon_gonder,
        otomatik_ekonomi,
        vergi_sistemi,
        mafia_board,
	premium_kontrol
    ]

    for loop in loops:
        try:
            if not loop.is_running():
                loop.start()
                print(f"{loop.coro.__name__} başlatıldı.")
        except Exception as e:
            print(f"{loop.coro.__name__} başlatma hatası: {e}")

    print("Tüm sistemler başarıyla başlatıldı.")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"].startswith("ticket_cevap_"):
            user_id = int(interaction.data["custom_id"].split("_")[-1])
            await interaction.response.send_modal(TicketCevapModal(user_id))

if __name__ == "__main__":
    import os

    token = os.getenv("TOKEN")

    if not token:
        print("TOKEN bulunamadı!")
        exit()

    keep_alive()
    bot.run(token)