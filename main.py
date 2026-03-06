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

ISLETMELER = {
    "maden": {"fiyat": 300000, "gelir": 6000},
    "ciftlik": {"fiyat": 450000, "gelir": 9000},
    "otel": {"fiyat": 900000, "gelir": 20000},
    "fabrika": {"fiyat": 2000000, "gelir": 45000},
    "bankasubesi": {"fiyat": 3500000, "gelir": 75000},
    "liman": {"fiyat": 5000000, "gelir": 110000},
    "sirket": {"fiyat": 8000000, "gelir": 180000},
    "holding": {"fiyat": 14000000, "gelir": 280000}
}

invite_cache = {}

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
                }
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

async def xp_ekle(user_id, miktar):

    user = get_user(user_id)

    xp = user.get("xp", 0)
    level = user.get("level", 1)

    xp += miktar
    gereken = level * 500

    while xp >= gereken:
        xp -= gereken
        level += 1
        gereken = level * 500

        # Level atlama ödülü
        collection.update_one(
            {"_id": str(user_id)},
            {"$inc": {"para": level * 1000}}
        )

    collection.update_one(
        {"_id": str(user_id)},
        {"$set": {"xp": xp, "level": level}}
    )

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

def get_rank_name(point):
    if point < 100:
        return "Bronz"
    elif point < 300:
        return "Gümüş"
    elif point < 600:
        return "Altın"
    elif point < 1000:
        return "Elmas"
    else:
        return "Efsane"

def enflasyon_orani():
    toplam = global_toplam_para()
    REFERANS = 5_000_000
    oran = toplam / REFERANS
    return max(0.5, min(5, oran))

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

@bot.command()
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

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def paragönder(ctx, member: discord.Member, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    sender = get_user(ctx.author.id)

    if sender["para"] < miktar:
        return await ctx.send("❌ Yetersiz bakiye")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar}}
    )

    collection.update_one(
        {"_id": str(member.id)},
        {"$inc": {"para": miktar}},
        upsert=True
    )

    await ctx.send(f"✅ {member.mention} kişisine {formatla(miktar)} EwoCoin gönderildi")
    await xp_ekle(ctx.author.id, 5)

MAX_BET = 100000

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cf(ctx, miktar: str):

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
        return await ctx.send("❌ En fazla 100.000 oynayabilirsin.")

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
    await gorev_kontrol(ctx.author.id, "cf", 1)
    await rozet_kontrol(ctx.author.id)

# level sistemi
@bot.command()
async def level(ctx):

    user = get_user(ctx.author.id)

    xp = user.get("xp", 0)
    level = user.get("level", 1)

    gereken = level * 100
    oran = int((xp / gereken) * 10)

    bar = "🟩" * oran + "⬜" * (10 - oran)

    embed = discord.Embed(
        title="🏆 Kullanıcı Profili",
        color=discord.Color.gold()
    )

    embed.add_field(name="Seviye", value=f"LVL {level}", inline=True)
    embed.add_field(name="XP", value=f"{xp} / {gereken}", inline=True)
    embed.add_field(name="İlerleme", value=bar, inline=False)

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

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

    MAX_BET = 100000
    user = get_user(ctx.author.id)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send("❌ Maksimum 100.000 oynayabilirsin.")

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

    await xp_ekle(ctx.author.id, 5)
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

    await xp_ekle(ctx.author.id, 5)
    await ctx.send(f"💰 Maaşını aldın! +{formatla(maas_miktari)} EwoCoin")

# gunluk 
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

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": odul},
            "$set": {"son_gunluk": simdi}
        }
    )

    await xp_ekle(ctx.author.id, 10)
    await ctx.send(f"🎁 Günlük ödülünü aldın! +{formatla(odul)} EwoCoin")




# BANKA SİSTEMİ

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def banka(ctx):
    user = get_user(ctx.author.id)
    faiz = int(user["banka"] * 0.05)  # %5 günlük faiz

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

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def bankaçek(ctx, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    user = get_user(ctx.author.id)

    if user["banka"] < miktar:
        return await ctx.send("❌ Banka bakiyeniz yeterli değil")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": miktar, "banka": -miktar}}
    )

    await ctx.send(f"🏦 {ctx.author.mention}, bankadan {formatla(miktar)} EwoCoin çektiniz")

# BANKAYATIR KOMUDU

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def bankayatır(ctx, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Geçersiz miktar")

    user = get_user(ctx.author.id)

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yok")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "banka": miktar}}
    )

    await ctx.send(f"🏦 {ctx.author.mention}, bankaya {formatla(miktar)} EwoCoin yatırdınız")

# YARDIM SİSTEMİ

from discord.ui import View, Button

@bot.command()
@commands.cooldown(1, 4, commands.BucketType.user)
async def yardım(ctx):

    ekonomi_embed = discord.Embed(
        title="💰 Ekonomi Komutları",
        description="""
q!param → Paranızı gösterir
q!paragönder @kişi miktar → Para gönderir
q!hesap → Hesap bilgilerinizi gösterir
q!level → Hesap Levelinizi gösterir
q!satınal <varlık> <miktar> → Varlık satın alır
q!sat <varlık> <miktar> → Varlık satar
q!ekonomi → Ekonomi durumunu gösterir
q!dilen → Dilenme komutu
q!gunluk → Günlük paranızı verir
q!maaş → Maaşınızı yatırır
""",
        color=discord.Color.green()
    )

    kumar_embed = discord.Embed(
        title="🎲 Kumar Komutları",
        description="""
q!cf miktar → Yazı tura
q!balıktut → Balık Oyunu
q!zar miktar → Zar atmaca
q!yuksekdusuk miktar yuksek&dusuk → Sayı bilmece 
q!slot miktar → Slot oyunu
q!blackjack miktar → Blackjack oyunu
""",
        color=discord.Color.red()
    )

    banka_embed = discord.Embed(
        title="🏦 Banka Komutları",
        description="""
q!banka → Banka hesabını gösterir
q!bankayatır miktar → Bankaya para yatır
q!bankaçek miktar → Bankadan para çek
""",
        color=discord.Color.gold()
    )

    meslek_embed = discord.Embed(
        title="💼 Meslek Komutları",
        description="""
q!meslekler → Meslekleri listeler
q!meslek al <meslek> → Meslek satın al
""",
        color=discord.Color.purple()
    )

    isletme_embed = discord.Embed(
        title="🏭 İşletme Komutları",
        description="""
q!işletmeler → Tüm işletmeleri gösterir
q!işletmeal <isim> <miktar> → İşletme satın al
q!işletmeyükselt <isim> → İşletmeni yükselt
q!işletmeparaçek → Biriken geliri toplar
q!işletmetop → Global en büyük sanayiciler
q!sigorta → 24 saatlik sigorta al
""",
        color=discord.Color.dark_teal()
    )

    diger_embed = discord.Embed(
        title="📊 Diğer Komutlar",
        description="""
q!gzenginler → Global en zenginler
q!szenginler → Sunucudaki en zenginler
q!düello @kullanıcı <bahis> → Başka kullanıcılarla düello yaparsınız
q!rank → Düello rankınızı gösterir
q!gdüellocular → En fazla WİN'e sahip 10 kişiyi sıralar
q!sdüellocular → Sunucuda En fazla WİN'e sahip 10 kişiyi sıralar
q!soygun → Başka kullanıcıyı soygun yap
q!enflasyon → Toplam EwoCoin miktarı
q!kasaaç <Kasaadi> → Kasa açar
q!market → Marketi gösterir
q!envanter → Envanteri gösterir
q!evlen @kullanıcı → Evlilik teklifi gönderir
q!boşan → Evliliği bitirir (evli olduğu kişiye servetinin %5'i tazminat öder)
q!göreval → Rastgele zor görev alır
q!görevler → Aktif görevini gösterir
q!rozetler → Tüm rozetleri ve kazanma şartlarını gösterir
q!rozetlerim → Sahip olduğun rozetleri gösterir
q!hesaprozetekle <rozet adı> → Hesapta görünecek rozeti seçer
q!davet → Botu sunucuna ekle
""",
        color=discord.Color.blurple()
    )

    # 🔥 YENİ EKLENEN EMBED
    yetkili_embed = discord.Embed(
        title="🛠️ Moderasyon Komutları (Botu Sunucusuna ekleyen yöneticiler için)",
        description="""
q!komutkapat → Bulunduğun kanalda bot komutlarını kapatır
q!komutaç → Bulunduğun kanalda bot komutlarını açar
q!prefix <yeni> → Sunucu prefixini değiştirir
q!prefixsifirla → Prefixi varsayılana döndürür
""",
        color=discord.Color.orange()
    )

    for e in [ekonomi_embed, kumar_embed, banka_embed, meslek_embed, isletme_embed, diger_embed, yetkili_embed]:
        e.set_footer(text="EwoBot Yardım Menüsü")

    view = View(timeout=None)

    ekonomi_button = Button(label="💰 Ekonomi", style=discord.ButtonStyle.green)
    kumar_button = Button(label="🎲 Kumar", style=discord.ButtonStyle.red)
    banka_button = Button(label="🏦 Banka", style=discord.ButtonStyle.blurple)
    meslek_button = Button(label="💼 Meslek", style=discord.ButtonStyle.gray)
    isletme_button = Button(label="🏭 İşletmeler", style=discord.ButtonStyle.green)
    diger_button = Button(label="📊 Diğer", style=discord.ButtonStyle.blurple)
    yetkili_button = Button(label="🛠️ Sunucu Moderasyon", style=discord.ButtonStyle.danger)

    async def ekonomi_callback(interaction):
        await interaction.response.edit_message(embed=ekonomi_embed, view=view)

    async def kumar_callback(interaction):
        await interaction.response.edit_message(embed=kumar_embed, view=view)

    async def banka_callback(interaction):
        await interaction.response.edit_message(embed=banka_embed, view=view)

    async def meslek_callback(interaction):
        await interaction.response.edit_message(embed=meslek_embed, view=view)

    async def isletme_callback(interaction):
        await interaction.response.edit_message(embed=isletme_embed, view=view)

    async def diger_callback(interaction):
        await interaction.response.edit_message(embed=diger_embed, view=view)

    async def yetkili_callback(interaction):
        await interaction.response.edit_message(embed=yetkili_embed, view=view)

    ekonomi_button.callback = ekonomi_callback
    kumar_button.callback = kumar_callback
    banka_button.callback = banka_callback
    meslek_button.callback = meslek_callback
    isletme_button.callback = isletme_callback
    diger_button.callback = diger_callback
    yetkili_button.callback = yetkili_callback

    view.add_item(ekonomi_button)
    view.add_item(kumar_button)
    view.add_item(banka_button)
    view.add_item(meslek_button)
    view.add_item(isletme_button)
    view.add_item(diger_button)
    view.add_item(yetkili_button)

    await ctx.send(embed=ekonomi_embed, view=view)

# Meslek ve fiyatları tanımla
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

# Meslekleri listele
@bot.command(name="meslekler")
@commands.cooldown(1, 4, commands.BucketType.user)
async def meslekler_cmd(ctx):
    embed = discord.Embed(title="💼 Mevcut Meslekler", color=discord.Color.purple())
    for isim, veri in meslekler.items():
        embed.add_field(name=isim, value=f"Fiyat: {veri['fiyat']} EwoCoin\nGünlük Maaş: {veri['maas']} EwoCoin", inline=False)
    embed.set_footer(text="q!meslek al <meslek> ile meslek alabilirsiniz")
    await ctx.send(embed=embed)

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

# =====================================================
# 👤 HESAP KOMUTU (TÜM VARLIKLAR GÖSTERİR)
# =====================================================

@bot.command()
async def hesap(ctx):
    try:
        # Kullanıcı verisini çek
        user = get_user(ctx.author.id)

        if not user:
            await ctx.send("❌ Kullanıcı verisi bulunamadı.")
            return

        # Güvenli veri çekimleri
        meslek = user.get("meslek", "Yok")
        maas = 0
        if "meslekler" in globals():
            maas = meslekler.get(meslek, {}).get("maas", 0)

        banka = user.get("banka", 0)
        para = user.get("para", 0)
        faiz = int(banka * 0.05)

        # Format fonksiyonu güvenliği
        def safe_format(x):
            try:
                return formatla(x)
            except:
                return str(x)

        embed = discord.Embed(
            title="👤 Hesap Bilgilerin",
            color=discord.Color.blue()
        )

        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        embed.add_field(name="💰 Nakit", value=safe_format(para), inline=False)
        embed.add_field(name="🏦 Banka", value=safe_format(banka), inline=False)
        embed.add_field(name="💼 Meslek", value=meslek, inline=False)
        embed.add_field(name="💵 Günlük Maaş", value=safe_format(maas), inline=False)
        embed.add_field(name="📈 Günlük Banka Faizi (%5)", value=safe_format(faiz), inline=False)

        # ================= PvP =================
        pvp = user.get("pvp", {}) or {}
        rank_point = pvp.get("rank_point", 0)
        win = pvp.get("win", 0)
        lose = pvp.get("lose", 0)

        try:
            rank_name = get_rank_name(rank_point)
        except:
            rank_name = "Unranked"

        embed.add_field(
            name="⚔️ Düello Rank",
            value=f"🏆 Rank: {rank_name}\n"
                  f"⭐ Puan: {rank_point}\n"
                  f"🥇 Win: {win} | ❌ Lose: {lose}",
            inline=False
        )

        # ================= Rozet =================
        aktif_rozet = user.get("aktif_rozet")
        if aktif_rozet:
            embed.add_field(name="👑 Aktif Rozet", value=aktif_rozet, inline=False)

        # ================= Görünüş =================
        envanter = user.get("envanter", {}) or {}

        gosteris = None

        for item in ["Elmas Görünüş", "Altın Görünüş", "Gümüş Görünüş", "Bronz Görünüş"]:
            if envanter.get(item, 0) > 0:
                gosteris = item

        if gosteris:
            embed.add_field(name="✨ Görünüş", value=gosteris, inline=False)

        # ================= Eş =================
        es_id = user.get("married_to")
        if es_id:
            try:
                es_user = bot.get_user(int(es_id)) or await bot.fetch_user(int(es_id))
                embed.add_field(name="💍 Eşi", value=es_user.name, inline=False)
            except:
                embed.add_field(name="💍 Eşi", value="Bilinmiyor", inline=False)

        # ================= Yatırımlar =================
        yatirimlar = user.get("yatirimlar", {}) or {}
        text = ""

        for varlik, adet in yatirimlar.items():
            if adet > 0:
                text += f"💎 {varlik.capitalize()}: {adet} adet\n"

        if not text:
            text = "Yatırım yok."

        embed.add_field(name="📦 Varlıkların", value=text, inline=False)

        # ================= İşletmeler =================
        isletmeler = user.get("isletmeler", {}) or {}
        isletme_text = ""

        for isim, veri in isletmeler.items():
            adet = veri.get("adet", 0)
            level = veri.get("level", 1)

            if adet > 0:
                isletme_text += f"🏭 {isim} x{adet} (Lv.{level})\n"

        if not isletme_text:
            isletme_text = "İşletmen yok."

        embed.add_field(name="🏭 İşletmelerin", value=isletme_text, inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        print("HESAP KOMUT HATASI:", e)
        await ctx.send("❌ Hesap bilgileri yüklenirken bir hata oluştu.")

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

# BLACK JACK

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
    await gorev_kontrol(ctx.author.id, "blackjack", 1)
    await rozet_kontrol(ctx.author.id)

# ZAR KOMUTU
@bot.command()
@commands.cooldown(1, 7, commands.BucketType.user)
async def zar(ctx, miktar: str):

    MAX_BET = 100000
    user = get_user(ctx.author.id)

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send("❌ Maksimum 100.000 oynayabilirsin.")

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
    await gorev_kontrol(ctx.author.id, "zar", 1)
    await rozet_kontrol(ctx.author.id)

# yuksek asagı
@bot.command()
@commands.cooldown(1, 8, commands.BucketType.user)
async def yuksekdusuk(ctx, miktar: str, secim: str):

    MAX_BET = 100000
    user = get_user(ctx.author.id)

    secim = secim.lower()

    if secim not in ["yuksek", "dusuk"]:
        return await ctx.send("❌ Seçim: yuksek / dusuk")

    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli miktar gir.")
        miktar = int(miktar)

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir.")

    if miktar > MAX_BET:
        return await ctx.send("❌ Maksimum 100.000 oynayabilirsin.")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar, "yuksekdusuk_sayisi": 1}}
    )

    await ctx.send("🎯 Sayı belirleniyor...")
    await asyncio.sleep(2)

    sayi = random.randint(1, 100)

    win_chance = hesapla_win_chance(user)
    kazandi = random.random() < win_chance

    if kazandi:
        kazanc = miktar * 2
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc, "toplam_kazanc": kazanc}}
        )
        sonuc = f"🎯 Sayı: {sayi}\n🎉 Kazandın! +{formatla(kazanc)}"
    else:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"toplam_kayip": miktar}}
        )
        sonuc = f"🎯 Sayı: {sayi}\n💀 Kaybettin!"

    await ctx.send(sonuc)

    await xp_ekle(ctx.author.id, 5)
    await gorev_kontrol(ctx.author.id, "yuksekdusuk", 1)
    await rozet_kontrol(ctx.author.id)

# ================== EKONOMİ KOMUTU ==================

@bot.command(name="ekonomi")
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

# ================== SAT KOMUTU ==================

@bot.command()
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
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Bu komutu tekrar kullanmak için {round(error.retry_after)} saniye beklemelisin!")
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
        await bot.change_presence(activity=discord.Game(name="q!yardım | q!davet | prefix: q!"))
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

# ------------------- GLOBAL / SUNUCU ÖZEL AYARLARI -------------------
DESTEK_SUNUCU_ID = 1471843922115301493
DESTEK_ROL_ID = 1474482319443361945
KATILIM_CIKIS_KANAL_ID = 1474485498415153374

@bot.event
async def on_member_join(member):
    if member.guild.id == DESTEK_SUNUCU_ID:
        rol = member.guild.get_role(DESTEK_ROL_ID)
        if rol:
            await member.add_roles(rol)
        kanal = bot.get_channel(KATILIM_CIKIS_KANAL_ID)
        if kanal:
            await kanal.send(f"✅ {member.mention} sunucuya katıldı!")

@bot.event
async def on_member_remove(member):
    if member.guild.id == DESTEK_SUNUCU_ID:
        kanal = bot.get_channel(KATILIM_CIKIS_KANAL_ID)
        if kanal:
            await kanal.send(f"❌ {member.mention} sunucudan ayrıldı!")

# Help kapatma 
@bot.command()
async def help(ctx):
    await ctx.send("❌ Yanlış Komut! Lütfen `q!yardım` yazınız.")

# =====================================================
# 🌍 GLOBAL EwoPlusCoin ZENGİNLER
# =====================================================

@bot.command()
async def gzenginler(ctx):

    tum_kullanicilar = collection.find()

    liste = []

    for user in tum_kullanicilar:
        para = user.get("para", 0)
        banka = user.get("banka", 0)
        toplam_servet = para + banka

        if toplam_servet > 0:
            liste.append((user["_id"], toplam_servet))

    # Büyükten küçüğe sırala
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
            embed.add_field(
                name=f"{i}. {uye.name}",
                value=f"💰 Serveti = {formatla(servet)} EwoCoin",
                inline=False
            )
        except:
            continue

    await ctx.send(embed=embed)

# =====================================================
# 🔁 10 DAKİKADA BİR GLOBAL EwoPlusCoin
# =====================================================

GLOBAL_ZENGINLER_KANAL_ID = 1474500301758267565
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
                uye = bot.get_user(int(user_id))  # FETCH YOK!
                if not uye:
                    continue

                embed.add_field(
                    name=f"{i}. {uye.name}",
                    value=f"💰 {formatla(servet)} EwoCoin",
                    inline=False
                )

        # Mesaj varsa edit
        if global_zenginler_mesaj_id:
            try:
                mesaj = await kanal.fetch_message(global_zenginler_mesaj_id)
                await mesaj.edit(embed=embed)
                return
            except:
                global_zenginler_mesaj_id = None

        # Yoksa yeni oluştur
        mesaj = await kanal.send(embed=embed)
        global_zenginler_mesaj_id = mesaj.id

    except Exception as e:
        print("Global zenginler hata:", e)


@otomatik_gzenginler.before_loop
async def before_global():
    await bot.wait_until_ready()

@bot.command()
async def szenginler(ctx):

    toplam_para = []

    for member in ctx.guild.members:
        info = collection.find_one({"_id": str(member.id)})
        if not info:
            continue

        toplam = info.get("para", 0) + info.get("banka", 0)
        toplam_para.append((member.name, toplam))

    sirali = sorted(toplam_para, key=lambda x: x[1], reverse=True)[:10]

    text = ""
    for i, (name, bakiye) in enumerate(sirali, 1):
        text += f"{i}. {name} - {formatla(bakiye)} EwoCoin\n"

    embed = discord.Embed(
        title=f"💰 {ctx.guild.name} En Zenginler",
        description=text or "Veri yok",
        color=discord.Color.gold()
    )

    await ctx.send(embed=embed)

# ------------------- q!enflasyon -------------------
@bot.command()
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

ENFLASYON_KANAL_ID = 1474499745257881762
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

# ------------------- ADMIN KOMUTLARI -------------------
ADMIN_ID = 1271933410251772017
kilitli_kanallar = set()

# ---------------- q!kitle / q!kitleaç ----------------
kilitli_kanallar = set()

@bot.command()
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
async def bakımbitti(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ Bu komutu kullanamazsın!")

    kanal = bot.get_channel(KANAL_ID)
    if kanal and ctx.guild.id == SUNUCU_ID:
        await kanal.send("@everyone ✅ EwoBotun bakımı bitmiştir, Bot tekrardan aktif!")

    await ctx.send("✅ Bakım modu sonlandırıldı! Kanal bilgilendirildi.")

# ---------------- DUYURU SİSTEMİ ; ----------------------

@bot.command()
async def duyuru(ctx, kanal: discord.TextChannel, *, mesaj):
    if ctx.author.id != 1271933410251772017:
        return

    await kanal.send(mesaj)
    await ctx.send("✅ Duyuru gönderildi.")

@bot.command()
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
async def önemliduyuru(ctx, *, mesaj):
    if ctx.author.id != 1271933410251772017:
        return

    baslangic_zaman = time.time()
    toplam_sunucu = len(bot.guilds)

    duyuru_embed = discord.Embed(
        title="🚨 EwoBot Önemli Duyuru",
        description=mesaj,
        color=discord.Color.dark_blue()
    )
    duyuru_embed.set_thumbnail(url=bot.user.avatar.url)
    duyuru_embed.set_footer(text="EwoBot Yönetimi | Önemli Bildirim")

    ilerleme_embed = discord.Embed(
        title="📡 Önemli Duyuru Gönderilmeye Başladı...",
        description=(
            f"🌍 Gezilen Sunucu: **0 / {toplam_sunucu}**\n"
            f"👥 Toplam Kullanıcı: **0**\n"
            f"📨 Başarılı DM: **0**\n"
            f"❌ Başarısız DM: **0**\n"
            f"⏳ Tahmini Kalan Süre: Hesaplanıyor..."
        ),
        color=discord.Color.dark_blue()
    )
    ilerleme_embed.set_thumbnail(url=bot.user.avatar.url)

    mesaj_obj = await ctx.send(embed=ilerleme_embed)

    tum_kullanicilar = set()
    gezilen_sunucu = 0

    # Sunucuları gez ve kullanıcıları topla
    for guild in bot.guilds:
        gezilen_sunucu += 1

        for member in guild.members:
            if not member.bot:
                tum_kullanicilar.add(member.id)

        ilerleme_embed.description = (
            f"🌍 Gezilen Sunucu: **{gezilen_sunucu} / {toplam_sunucu}**\n"
            f"👥 Toplam Kullanıcı (Benzersiz): **{len(tum_kullanicilar)}**\n"
            f"📨 Başarılı DM: **0**\n"
            f"❌ Başarısız DM: **0**\n"
            f"⏳ Tahmini Kalan Süre: Hesaplanıyor..."
        )

        await mesaj_obj.edit(embed=ilerleme_embed)

    toplam_kullanici = len(tum_kullanicilar)
    basarili = 0
    basarisiz = 0

    # DM gönderme
    for index, user_id in enumerate(tum_kullanicilar, start=1):
        try:
            uye = await bot.fetch_user(user_id)
            await uye.send(embed=duyuru_embed)
            basarili += 1
        except:
            basarisiz += 1

        # Tahmini süre hesaplama
        gecen_sure = time.time() - baslangic_zaman
        ortalama_sure = gecen_sure / index
        kalan_kisi = toplam_kullanici - index
        tahmini_kalan = int(ortalama_sure * kalan_kisi)

        if index % 5 == 0 or index == toplam_kullanici:
            ilerleme_embed.description = (
                f"🌍 Gezilen Sunucu: **{toplam_sunucu} / {toplam_sunucu}**\n"
                f"👥 Toplam Kullanıcı: **{toplam_kullanici}**\n"
                f"📨 Başarılı DM: **{basarili}**\n"
                f"❌ Başarısız DM: **{basarisiz}**\n"
                f"⏳ Tahmini Kalan Süre: **{tahmini_kalan} saniye**"
            )

            await mesaj_obj.edit(embed=ilerleme_embed)
            await asyncio.sleep(0.4)

    toplam_sure = int(time.time() - baslangic_zaman)

    final_embed = discord.Embed(
        title="📊 Önemli Duyuru Tamamlandı",
        description=(
            f"🌍 Toplam Sunucu: **{toplam_sunucu}**\n"
            f"👥 Toplam Benzersiz Kullanıcı: **{toplam_kullanici}**\n\n"
            f"📨 Başarılı DM: **{basarili}**\n"
            f"❌ Başarısız DM: **{basarisiz}**\n\n"
            f"⏱ Toplam Süre: **{toplam_sure} saniye**"
        ),
        color=discord.Color.green()
    )

    final_embed.set_thumbnail(url=bot.user.avatar.url)
    final_embed.set_footer(text="EwoBot Yönetimi | Yayın Sistemi")

    await mesaj_obj.edit(embed=final_embed)

# Loglama Sistemi ------------------------------
DESTEK_SUNUCU_ID = 1471843922115301493
LOG_KANAL_ID = 1474500638581854351
EKLEME_LOG_KANAL = 1474500594554372247
PANEL_KANAL_ID = 1474500454653100142
PANEL_SUNUCU_ID = 1471843922115301493
PANEL_LOG_KANAL = 1474501447721943061

@bot.command()
async def logpanel(ctx):
    if ctx.guild.id != PANEL_SUNUCU_ID:
        return

    if ctx.channel.id != PANEL_KANAL_ID:
        return

    view = View()

    async def logs_ac(interaction):
        kanal = bot.get_channel(PANEL_LOG_KANAL)
        await kanal.send("📢 Admin log sistemi aktif edildi.")

        await interaction.response.send_message("✅ Log aktif edildi.", ephemeral=True)

    buton = Button(label="Logları Aktif Et", style=discord.ButtonStyle.green)
    buton.callback = logs_ac

    view.add_item(buton)

    await ctx.send("⚙️ Admin Log Paneli", view=view)

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

MILESTONE_KANAL = 1474728861920137276
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

# Mesaj silme
@bot.event
async def on_message_delete(message):
    if message.guild and message.guild.id == DESTEK_SUNUCU_ID:
        kanal = bot.get_channel(LOG_KANAL_ID)
        if kanal:
            embed = discord.Embed(
                title="🗑️ Mesaj Silindi",
                description=f"{message.author.mention} tarafından gönderilen mesaj silindi.",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=message.author.avatar.url if message.author.avatar else None)
            embed.add_field(name="Kanal", value=message.channel.mention)
            embed.add_field(name="Mesaj", value=message.content or "Görsel / Embed")
            embed.set_footer(text=f"ID: {message.id}")
            await kanal.send(embed=embed)

# Mesaj düzenleme
@bot.event
async def on_message_edit(before, after):
    if after.guild and after.guild.id == DESTEK_SUNUCU_ID and before.content != after.content:
        kanal = bot.get_channel(LOG_KANAL_ID)
        if kanal:
            embed = discord.Embed(
                title="✏️ Mesaj Düzenlendi",
                description=f"{after.author.mention} mesajını düzenledi.",
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=after.author.avatar.url if after.author.avatar else None)
            embed.add_field(name="Kanal", value=after.channel.mention)
            embed.add_field(name="Eski Mesaj", value=before.content or "Görsel / Embed")
            embed.add_field(name="Yeni Mesaj", value=after.content or "Görsel / Embed")
            embed.set_footer(text=f"ID: {after.id}")
            await kanal.send(embed=embed)

# Rol ekleme / çıkarma
@bot.event
async def on_member_update(before, after):
    if after.guild.id == DESTEK_SUNUCU_ID:
        kanal = bot.get_channel(LOG_KANAL_ID)
        if kanal:
            # Rol eklendi
            yeni_roller = set(after.roles) - set(before.roles)
            for rol in yeni_roller:
                embed = discord.Embed(
                    title="➕ Rol Eklendi",
                    description=f"{after.mention} kişisine rol verildi.",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=after.avatar.url if after.avatar else None)
                embed.add_field(name="Rol", value=rol.mention)
                embed.set_footer(text=f"ID: {after.id}")
                await kanal.send(embed=embed)

            # Rol çıkarıldı
            silinen_roller = set(before.roles) - set(after.roles)
            for rol in silinen_roller:
                embed = discord.Embed(
                    title="➖ Rol Çıkarıldı",
                    description=f"{after.mention} kişisinin rolü alındı.",
                    color=discord.Color.dark_red()
                )
                embed.set_thumbnail(url=after.avatar.url if after.avatar else None)
                embed.add_field(name="Rol", value=rol.mention)
                embed.set_footer(text=f"ID: {after.id}")
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
EKONOMI_LOG_KANAL = 1474499591238848555

# =====================================================
# YARDIMCI FONKSİYON
# =====================================================

def parse_int(value: str):
    return int(value.replace(".", "").replace(",", "").strip())

# =====================================================
# ANA KOMUT
# =====================================================

@bot.command()
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
# 🛒 MARKET SİSTEMİ (YÜZÜK + GÖSTERİŞ + ARAÇGEREÇLER)
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
    await ctx.send(embed=embed, view=MarketMainView())


def market_ana_embed():
    return discord.Embed(
        title="🛒 EwoBot Market",
        description=(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎁 **KASA KATEGORİSİ**\n\n"
            "🟤 Bronz Kasa\n"
            "⚪ Gümüş Kasa\n"
            "🟡 Altın Kasa\n"
            "💎 Elmas Kasa\n"
            "🌟 Premium Kasa\n"
            "🔥 EwoPlus Kasa\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🕶 **SOYGUN KATEGORİSİ**\n\n"
            "🔫 Silah\n"
            "🛡 Özel Koruma\n"
            "🧰 Özel Araçgereçler\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎣 **EKONOMİ KATEGORİSİ**\n\n"
            "🎣 Olta\n"
            "💍 Yüzük\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👑 **GÖSTERİŞ KATEGORİSİ**\n\n"
            "🥉 Bronz Görünüş\n"
            "🥈 Gümüş Görünüş\n"
            "🥇 Altın Görünüş\n"
            "💎 Elmas Görünüş\n"
        ),
        color=discord.Color.dark_blue()
    )


# ------------------- ANA MENÜ -------------------

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
            view=SoygunMarketView()
        )

    @discord.ui.button(label="🎣 Ekonomi", style=discord.ButtonStyle.success)
    async def ekonomi(self, interaction, button):
        await interaction.response.edit_message(
            embed=ekonomi_market_embed(),
            view=EkonomiMarketView()
        )

    @discord.ui.button(label="👑 Gösteriş", style=discord.ButtonStyle.secondary)
    async def gosteris(self, interaction, button):
        await interaction.response.edit_message(
            embed=gosteris_embed(),
            view=GosterisView()
        )


# ------------------- EMBEDLER -------------------

def kasa_embed():
    return discord.Embed(
        title="🎁 Kasa Kategorisi",
        description=(
            "Bronz Kasa - 500\n"
            "Gümüş Kasa - 2000\n"
            "Altın Kasa - 5000\n"
            "Elmas Kasa - 15000\n"
            "Premium Kasa - 30000\n"
            "EwoPlus Kasa - 60000"
        ),
        color=discord.Color.gold()
    )


def soygun_embed():
    return discord.Embed(
        title="🕶 Soygun Ürünleri",
        description=(
            "Silah - 15000\n"
            "Özel Koruma - 20000\n"
            "Özel Araçgereçler - 750000"
        ),
        color=discord.Color.red()
    )


def ekonomi_market_embed():
    return discord.Embed(
        title="🎣 Ekonomi Ürünleri",
        description="Olta - 1000\nYüzük - 75000",
        color=discord.Color.blue()
    )


def gosteris_embed():
    return discord.Embed(
        title="👑 Gösteriş Ürünleri",
        description=(
            "Bronz Görünüş - 500000\n"
            "Gümüş Görünüş - 2000000\n"
            "Altın Görünüş - 5000000\n"
            "Elmas Görünüş - 15000000"
        ),
        color=discord.Color.purple()
    )


# ------------------- GÖSTERİŞ VIEW -------------------

class GosterisView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bronz Görünüş", style=discord.ButtonStyle.secondary)
    async def bronz(self, interaction, button):
        await satin_al(interaction, "Bronz Görünüş")

    @discord.ui.button(label="Gümüş Görünüş", style=discord.ButtonStyle.secondary)
    async def gumus(self, interaction, button):
        await satin_al(interaction, "Gümüş Görünüş")

    @discord.ui.button(label="Altın Görünüş", style=discord.ButtonStyle.secondary)
    async def altin(self, interaction, button):
        await satin_al(interaction, "Altın Görünüş")

    @discord.ui.button(label="Elmas Görünüş", style=discord.ButtonStyle.secondary)
    async def elmas(self, interaction, button):
        await satin_al(interaction, "Elmas Görünüş")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):
        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )


# ------------------- SATIN AL -------------------

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
            "$inc": {
                "para": -fiyat,
                f"envanter.{urun}": 1
            }
        }
    )

    await interaction.response.send_message(
        f"✅ {urun} satın alındı!",
        ephemeral=True
    )

# Envanter Komutu
@bot.command()
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

# kasa aç 
@bot.command()
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

# İŞLETME SİSTEMİ
@bot.command()
async def işletmeler(ctx):

    embed = discord.Embed(
        title="🏭 Aktif İşletmeler",
        description="Pasif gelir sağlayan tüm işletmeler aşağıdadır:",
        color=discord.Color.dark_teal()
    )

    embed.add_field(
        name="🪨 Maden",
        value="Fiyat: 300.000\nSaatlik: 4.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🌾 Ciftlik",
        value="Fiyat: 450.000\nSaatlik: 7.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🏨 Otel",
        value="Fiyat: 900.000\nSaatlik: 14.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🏭 Fabrika",
        value="Fiyat: 2.000.000\nSaatlik: 32.500\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🏦 Bankasubesi",
        value="Fiyat: 3.500.000\nSaatlik: 52.500\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🚢 Liman",
        value="Fiyat: 5.000.000\nSaatlik: 87.500\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="🏢 Sirket",
        value="Fiyat: 8.000.000\nSaatlik: 148.750\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="👑 Holding",
        value="Fiyat: 14.000.000\nSaatlik: 225.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="👑Teknolojiparkı",
        value="Fiyat: 35.000.000\nSaatlik: 275.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="👑 Megafabrika",
        value="Fiyat: 100.000.000\nSaatlik: 330.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="👑 Globalsirket",
        value="Fiyat: 500.000.000\nSaatlik: 485.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.add_field(
        name="👑 Uzaymadeni",
        value="Fiyat: 2.000.000.000\nSaatlik: 520.000\nYükseltme: Fiyat x %40 x Level",
        inline=False
    )

    embed.set_thumbnail(url=bot.user.avatar.url)

    embed.set_footer(
        text="🔼 Örnek: Maden Lv1→2 = 120k | Lv2→3 = 240k | Level arttıkça maliyet artar."
    )

    await ctx.send(embed=embed)

# işletme top
@bot.command()
async def işletmetop(ctx):

    users = collection.find({}, {"isletmeler": 1})
    siralama = []

    for user in users:
        isletmeler = user.get("isletmeler", {})
        toplam_deger = 0

        for isim, veri in isletmeler.items():
            adet = veri.get("adet", 0)
            level = veri.get("level", 1)

            if isim not in ISLETMELER:
                continue

            fiyat = ISLETMELER[isim]["fiyat"]

            # Gerçek şirket değeri hesabı
            deger = adet * fiyat * (1 + (level - 1) * 0.20)
            toplam_deger += deger

        siralama.append((user["_id"], int(toplam_deger)))

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
            value=f"Toplam İşletme Değeri: {formatla(deger)}",
            inline=False
        )

    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="EwoBot Global İşletme Sıralaması")

    await ctx.send(embed=embed)

@bot.command()
async def işletmeal(ctx, isim: str, miktar: int = 1):

    isim = isim.lower()
    user = get_user(ctx.author.id)

    if isim not in ISLETMELER:
        return await ctx.send("❌ Geçersiz işletme.")

    if miktar <= 0:
        return await ctx.send("❌ Miktar 1 veya büyük olmalı.")

    mevcut = user.get("isletmeler", {}).get(isim, {}).get("adet", 0)

    # TÜM İŞLETMELER İÇİN MAX 10 SINIRI
    if mevcut >= 10:
        return await ctx.send("❌ Bu işletmeden en fazla **10 tane** alabilirsin.")

    # HOLDİNG ÖZEL FİYAT SİSTEMİ
    if isim == "holding":

        if mevcut == 0:
            fiyat = 14000000
        else:
            fiyat = 20000000 + (mevcut - 1) * 5000000

        if user["para"] < fiyat:
            return await ctx.send(f"❌ {formatla(fiyat)} gerekli.")

        sonraki = 20000000 + mevcut * 5000000

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {
                "$inc": {
                    "para": -fiyat,
                    f"isletmeler.{isim}.adet": 1
                },
                "$set": {
                    f"isletmeler.{isim}.level": 1
                }
            }
        )

        await ctx.send(
            f"👑 **{mevcut+1}. Holding satın alındı!**\n"
            f"💰 Ödenen: {formatla(fiyat)}\n"
            f"📈 Sonraki holding fiyatı: {formatla(sonraki)}"
        )
        return

    # DİĞER İŞLETMELER
    fiyat = ISLETMELER[isim]["fiyat"]

    if user["para"] < fiyat:
        return await ctx.send(f"❌ {formatla(fiyat)} gerekli.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": -fiyat,
                f"isletmeler.{isim}.adet": 1
            },
            "$set": {
                f"isletmeler.{isim}.level": 1
            }
        }
    )

    await ctx.send(
        f"🏭 **{isim.capitalize()} satın alındı!**\n"
        f"💰 Ödenen: {formatla(fiyat)}\n"
        f"📦 Toplam: {mevcut+1}/10"
    )

@bot.command()
async def işletmeyükselt(ctx, *, isim: str):

    isim = isim.lower()
    user = get_user(ctx.author.id)

    if "isletmeler" not in user or isim not in user["isletmeler"]:
        return await ctx.send("❌ Bu işletmeye sahip değilsin.")

    veri = user["isletmeler"][isim]
    level = veri.get("level", 1)

    if isim not in ISLETMELER:
        return await ctx.send("❌ Geçersiz işletme.")

    temel_fiyat = ISLETMELER[isim]["fiyat"]

    # 🔼 Yükseltme maliyeti formülü
    maliyet = int(temel_fiyat * 0.40 * level)

    if user.get("para", 0) < maliyet:
        return await ctx.send(
            f"❌ Yetersiz bakiye.\n"
            f"Gerekli: {formatla(maliyet)}"
        )

    # Level arttır
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": -maliyet,
                f"isletmeler.{isim}.level": 1
            }
        }
    )

    yeni_level = level + 1

    embed = discord.Embed(
        title="🔼 İşletme Yükseltildi!",
        color=discord.Color.green()
    )

    embed.add_field(
        name="🏭 İşletme",
        value=isim.capitalize(),
        inline=False
    )

    embed.add_field(
        name="📊 Yeni Level",
        value=f"Level {yeni_level}",
        inline=False
    )

    embed.add_field(
        name="💸 Ödenen",
        value=formatla(maliyet),
        inline=False
    )

    embed.add_field(
        name="📈 Gelir Artışı",
        value="%10 arttı",
        inline=False
    )

    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="Level arttıkça yükseltme maliyeti artar.")

    await ctx.send(embed=embed)

import time

@bot.command()
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
async def işletmeparaçek(ctx):

    user = get_user(ctx.author.id)
    simdi = int(time.time())

    son = user.get("son_isletme_toplama", 0)

    if son == 0:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"son_isletme_toplama": simdi}}
        )
        return await ctx.send("⏳ Sistem başlatıldı. Gelir 1 saat sonra oluşacak.")

    saat = (simdi - son) // 3600

    if saat <= 0:
        return await ctx.send("⏳ Henüz gelir oluşmadı.")

    # 🔥 26 SAAT SONRA GELİR YANAR
    if saat > 26:

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": {"son_isletme_toplama": simdi}}
        )

        return await ctx.send(
            "🔥 **Geliri zamanında çekmedin!**\n"
            "Biriken tüm işletme geliri **yanıp gitti.**"
        )

    # ⏱ MAX 24 SAAT
    if saat > 24:
        saat = 24

    toplam = 0

    for isim, veri in user.get("isletmeler", {}).items():

        adet = veri.get("adet", 0)
        level = veri.get("level", 1)

        if isim not in ISLETMELER:
            continue

        base = ISLETMELER[isim]["gelir"]

        gelir = int(base * adet * saat * (1 + (level - 1) * 0.10))
        toplam += gelir

    if toplam <= 0:
        return await ctx.send("❌ İşletmen yok.")

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {"para": toplam},
            "$set": {"son_isletme_toplama": simdi}
        }
    )

    embed = discord.Embed(
        title="🏭 İşletme Geliri Toplandı",
        description=f"🕒 Süre: {saat} saat\n💰 Kazanç: {formatla(toplam)}",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed)

# EVLENME

@bot.command(name="evlen")
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

@tasks.loop(hours=1)
async def otomatik_gduellocular():

    channel = bot.get_channel(1476245925382066312)
    if not channel:
        return

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
        color=discord.Color.gold()
    )

    # Var olan mesajı bul ve güncelle
    async for msg in channel.history(limit=20):
        if msg.author == bot.user and msg.embeds:
            await msg.edit(embed=embed)
            return

    await channel.send(embed=embed)

@bot.command()
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

    # DM'de serbest
    if not ctx.guild:
        return True

    if await kanal_kilitli_mi(ctx.guild.id, ctx.channel.id):
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

@tasks.loop(hours=24)
async def vergi_sistemi():

    users = collection.find()

    for user in users:

        nakit = user["para"]
        banka = user["banka"]

        isletme_degeri = 0

        for isim, data in user.get("isletmeler", {}).items():
            fiyat = ISLETME_FIYATLARI.get(isim,0)
            adet = data["adet"]

            isletme_degeri += fiyat * adet

        servet = nakit + banka + isletme_degeri

        if servet >= 5000000:

            vergi = int(servet * 0.05)

            collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {"para": -vergi}}
            )

@bot.command()
@commands.cooldown(1, 750, commands.BucketType.user)
async def baskın(ctx, member: discord.Member, isletme):

    if member.bot or member == ctx.author:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Geçersiz hedef.")

    user = get_user(ctx.author.id)
    hedef = get_user(member.id)

    if user["envanter"].get("Özel Araçgereçler",0) <= 0:
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Baskın için **Özel Araçgereçler** lazım!")

    if isletme not in hedef.get("isletmeler", {}):
        ctx.command.reset_cooldown(ctx)
        return await ctx.send("❌ Bu kişinin böyle bir işletmesi yok!")

    basari = 0.45

    gelir = isletme_geliri_hesapla(hedef, isletme)

    if random.random() < basari:

        calinan = int(gelir * 0.40)

        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"para": -calinan}}
        )

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": calinan}}
        )

        mesaj = f"🚨 Baskın başarılı! {formatla(calinan)} EwoCoin çaldın!"

    else:

        ceza = 200000

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": -ceza}}
        )

        mesaj = f"👮 Polis seni yakaladı! {formatla(ceza)} ceza."

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"envanter.Özel Araçgereçler": -1}}
    )

    await ctx.send(mesaj)

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


# Bot tamamen hazır olmadan loop başlamasın
@duel_timeout_checker.before_loop
async def before_duel_timeout_checker():
    await bot.wait_until_ready()

# =====================================================
# BOT READY (STABİL & TEMİZ)
# =====================================================

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

    # LOOPLAR
    loops = [
        duel_timeout_checker,
        durum_degistir,
        otomatik_gzenginler,
        enflasyon_gonder,
        otomatik_ekonomi
    ]

    for loop in loops:
        try:
            if not loop.is_running():
                loop.start()
                print(f"{loop.coro.__name__} başlatıldı.")
        except Exception as e:
            print(f"{loop.coro.__name__} başlatma hatası: {e}")


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