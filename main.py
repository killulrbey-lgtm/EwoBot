# ================= IMPORTS =================
import discord
from discord.ext import commands, tasks
import random
import asyncio
import os
from pymongo import MongoClient, ReturnDocument
from flask import Flask
from threading import Thread

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

# ================= BOT =================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

def get_prefix(bot, message):
    prefixes = [
        "q!",
        "Q!",
        "q",
        "Q",
        "ewo ",
        "Ewo ",
        "!"
    ]
    return commands.when_mentioned_or(*prefixes)(bot, message)

bot = commands.Bot(
    command_prefix=get_prefix,
    case_insensitive=True,
    intents=intents,
    help_command=None        # 🔥 Default help kapalı
)

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
    "EwoPlusCoin": 500000,
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
                "para": 1000,
                "banka": 0,
                "meslek": "İşsiz",
                "envanter": {
                    "Bronz Kasa": 0,
                    "Gümüş Kasa": 0,
                    "Altın Kasa": 0,
                    "Elmas Kasa": 0,
                    "Premium Kasa": 0,
                    "EwoPlus Kasa": 0,
                    "Silah": 0,
                    "Özel Koruma": 0,
                    "Olta": 0
                },
                "yatirimlar": {
                    "Altın": 0,
                    "EwoPlusCoin": 0,
                    "Bitcoin": 0,
                    "Elmas": 0,
                    "Dolar": 0,
                    "Gümüş": 0
                }
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

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

MAX_BET = 100000

@bot.command()
@commands.cooldown(1, 5, commands.BucketType.user)
async def cf(ctx, miktar: str):

    user = get_user(ctx.author.id)

    # ALL sistemi
    if miktar.lower() == "all":
        miktar = min(user["para"], MAX_BET)
    else:
        if not miktar.isdigit():
            return await ctx.send("❌ Geçerli bir miktar gir.")

        miktar = int(miktar)

    if miktar > MAX_BET:
        return await ctx.send("❌ En fazla 100.000 EwoCoin ile oynayabilirsin.")

    if miktar <= 0:
        return await ctx.send("❌ Geçerli bir miktar gir.")

    if user["para"] < miktar:
        return await ctx.send("❌ Yeterli paran yok.")

    # Önce bahis düşülür (atomic)
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar}}
    )

    await ctx.send(f"🪙 {ctx.author.mention} {formatla(miktar)} EwoCoin ile yazı tura oynuyor...")
    await asyncio.sleep(2)

    # %50 şans
    if random.choice([True, False]):
        kazanc = miktar * 2

        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc}}
        )

        await ctx.send(f"🎉 Kazandın! +{formatla(kazanc)} EwoCoin")
    else:
        await ctx.send(f"💀 Kaybettin! -{formatla(miktar)} EwoCoin")

# =====================================================
# 🎰 SLOT KOMUTU (YENİ ORAN SİSTEMİ - FİNAL)
# %20 = 3 aynı (x3)
# %35 = 2 aynı (x2)
# %45 = 1 eşleşme ( %70 kayıp / %30 iade )
# =====================================================

@bot.command()
@commands.cooldown(1, 15, commands.BucketType.user)
async def slot(ctx, miktar):

    user = get_user(ctx.author.id)

    # =========================
    # 💰 MİKTAR KONTROL
    # =========================
    if str(miktar).lower() == "all":
        miktar = user["para"]
    else:
        try:
            miktar = int(miktar)
        except:
            return await ctx.send("❌ Geçerli miktar gir!")

    if miktar <= 0:
        return await ctx.send("❌ Geçerli miktar gir!")

    if miktar > 100000:
        return await ctx.send("❌ Slotta maksimum 100.000 oynayabilirsin!")

    if user["para"] < miktar:
        return await ctx.send("❌ Paran yetmiyor.")

    # =========================
    # 💸 PARAYI DÜŞ
    # =========================
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -miktar}}
    )

    msg = await ctx.send("🎰 Slot dönüyor...")
    await asyncio.sleep(2)

    emojis = ["🍒", "🍋", "🍉", "⭐"]

    ihtimal = random.randint(1, 100)
    kazanc = 0

    # =========================
    # 🎯 3 AYNI (%20)
    # =========================
    if ihtimal <= 20:
        sembol = random.choice(emojis)
        result = [sembol, sembol, sembol]
        kazanc = miktar * 3

    # =========================
    # 🎯 2 AYNI (%35)
    # =========================
    elif ihtimal <= 55:  # 20 + 35 = 55
        sembol = random.choice(emojis)
        farkli = random.choice([e for e in emojis if e != sembol])
        result = [sembol, sembol, farkli]
        random.shuffle(result)
        kazanc = miktar * 2

    # =========================
    # 🎯 1 EŞLEŞME (%45)
    # =========================
    else:
        # tamamen karışık
        result = random.sample(emojis, 3)

        # %30 iade / %70 kayıp
        if random.randint(1, 100) <= 30:
            kazanc = miktar  # iade
        else:
            kazanc = 0

    sonuc = " | ".join(result)

    # =========================
    # 💵 KAZANÇ EKLE
    # =========================
    if kazanc > 0:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": {"para": kazanc}}
        )
        text = f"🎉 Kazandın! +{formatla(kazanc)}"
    else:
        text = "💀 Kaybettin."

    await msg.edit(content=f"{sonuc}\n{text}")

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
    # Embedler kategorilere göre
    ekonomi_embed = discord.Embed(
        title="💰 Ekonomi Komutları",
        description="""
q!param → Paranızı gösterir
q!paragönder @kişi miktar → Para gönderir
q!hesap → Hesap bilgilerinizi gösterir
q!satınal <varlık> <miktar> → Varlık satın alır
q!sat <varlık> <miktar> → Varlık satar
q!ekonomi → Ekonomi durumunu gösterir
""",
        color=discord.Color.green()
    )

    kumar_embed = discord.Embed(
        title="🎲 Kumar Komutları",
        description="""
q!cf miktar → Yazı tura
q!balıktut → Balık Oyunu
q!slot miktar → Slot oyunu
q!dilen → Dilenme komutu
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

    diger_embed = discord.Embed(
        title="📊 Diğer Komutlar",
        description="""
q!gzenginler → Global en zenginler
q!szenginler → Sunucudaki en zenginler
q!soygun → Başka kullanıcıyı soygun yap
q!enflasyon → Toplam EwoCoin miktarı
q!kasaaç <Kasaadi> → Kasalarınızdan birisini açar
q!market → Satılan Ürünleri gösterir ve almanızı sağlar
q!envanter → Satın aldığınız ürünleri gösterir
q!davet → Botu sunucuna ekle
""",
        color=discord.Color.blurple()
    )

    # Footer
    for e in [ekonomi_embed, kumar_embed, banka_embed, meslek_embed, diger_embed]:
        e.set_footer(text="EwoBot Yardım Menüsü")

    # Butonlar
    view = View()
    ekonomi_button = Button(label="💰 Ekonomi", style=discord.ButtonStyle.green)
    kumar_button = Button(label="🎲 Kumar", style=discord.ButtonStyle.red)
    banka_button = Button(label="🏦 Banka", style=discord.ButtonStyle.blurple)
    meslek_button = Button(label="💼 Meslek", style=discord.ButtonStyle.gray)
    diger_button = Button(label="📊 Diğer", style=discord.ButtonStyle.blurple)

    # Callbackler
    async def ekonomi_callback(interaction):
        await interaction.response.edit_message(embed=ekonomi_embed, view=view)

    async def kumar_callback(interaction):
        await interaction.response.edit_message(embed=kumar_embed, view=view)

    async def banka_callback(interaction):
        await interaction.response.edit_message(embed=banka_embed, view=view)

    async def meslek_callback(interaction):
        await interaction.response.edit_message(embed=meslek_embed, view=view)

    async def diger_callback(interaction):
        await interaction.response.edit_message(embed=diger_embed, view=view)

    # Callbackleri ata
    ekonomi_button.callback = ekonomi_callback
    kumar_button.callback = kumar_callback
    banka_button.callback = banka_callback
    meslek_button.callback = meslek_callback
    diger_button.callback = diger_callback

    # Butonları ekle
    view.add_item(ekonomi_button)
    view.add_item(kumar_button)
    view.add_item(banka_button)
    view.add_item(meslek_button)
    view.add_item(diger_button)

    await ctx.send(embed=ekonomi_embed, view=view)

# Meslek ve fiyatları tanımla
meslekler = {
    "Cumhurbaşkanı": {"fiyat": 1_000_000, "maas": 50_000},
    "Mafya Babası": {"fiyat": 750_000, "maas": 42_750},
    "Mafya": {"fiyat": 600_000, "maas": 38_450},
    "Hacker": {"fiyat": 500_000, "maas": 32_250},
    "Pilot": {"fiyat": 300_000, "maas": 28_000},
    "Avukat": {"fiyat": 175_000, "maas": 24_500},
    "Doktor": {"fiyat": 100_000, "maas": 21_350},
    "Yazılım Geliştiricisi": {"fiyat": 80_000, "maas": 18_260},
    "Çöpçü": {"fiyat": 40_000, "maas": 13_250},
    "İşsiz": {"fiyat": 1, "maas": 2_000},
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
    user = get_user(ctx.author.id)

    meslek = user.get("meslek", "Yok")
    maas = meslekler.get(meslek, {}).get("maas", 0)
    faiz = int(user.get("banka", 0) * 0.05)

    embed = discord.Embed(
        title="👤 Hesap Bilgilerin",
        color=discord.Color.blue()
    )

    embed.set_thumbnail(url=ctx.author.avatar.url if ctx.author.avatar else None)

    embed.add_field(name="💰 Nakit", value=formatla(user.get("para", 0)), inline=False)
    embed.add_field(name="🏦 Banka", value=formatla(user.get("banka", 0)), inline=False)
    embed.add_field(name="💼 Meslek", value=meslek, inline=False)
    embed.add_field(name="💵 Günlük Maaş", value=formatla(maas), inline=False)
    embed.add_field(name="📈 Günlük Banka Faizi (%5)", value=formatla(faiz), inline=False)

    # =========================
    # 📦 VARLIKLAR (CASE FIX)
    # =========================
    yatirimlar = user.get("yatirimlar", {})
    text = ""

    for varlik, adet in yatirimlar.items():
        if adet > 0:
            text += f"💎 {varlik.capitalize()}: {adet} adet\n"

    if text == "":
        text = "Yatırım yok."

    embed.add_field(name="📦 Varlıkların", value=text, inline=False)

    await ctx.send(embed=embed)

# Dilenme komutu
@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def dilen(ctx):
    user = economy_col.find_one({"_id": str(ctx.author.id)})

    if not user:
        economy_col.insert_one({
            "_id": str(ctx.author.id),
            "para": 0,
            "banka": 0,
            "varliklar": {}
        })
        user = economy_col.find_one({"_id": str(ctx.author.id)})

    kazanilan = random.randint(100, 500)

    economy_col.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": kazanilan}}
    )

    await ctx.send(f"💰 {ctx.author.mention} dilenerek **{kazanilan}₺** kazandı!")

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

    user = get_user(ctx.author.id)

    varliklar = {
        "altın": 50000,
        "ewopluscoin": 500000,
        "bitcoin": 240000,
        "elmas": 80000,
        "dolar": 4500,
        "gümüş": 35000
    }

    varlik_key = varlik_adi.lower()

    if varlik_key not in varliklar:
        return await ctx.send("❌ Böyle bir varlık yok.")

    fiyat = varliklar[varlik_key]
    toplam = fiyat * miktar

    if user["para"] < toplam:
        return await ctx.send("❌ Paran yetmiyor.")

    # Para düş
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {"para": -toplam}}
    )

    # Yatırım ekle
    collection.update_one(
        {"_id": str(ctx.author.id)},
        {"$inc": {f"yatirimlar.{varlik_adi.capitalize()}": miktar}}
    )

    await ctx.send(f"✅ {miktar} adet {varlik_adi.capitalize()} satın alındı.")

# ================== SAT KOMUTU ==================

@bot.command(name="sat")
async def varlik_sat(ctx, varlik: str, miktar: int):

    if miktar <= 0:
        return await ctx.send("❌ Miktar 1 veya daha büyük olmalı.")

    varlik = varlik.capitalize()

    if varlik not in varsayilan_varlikler:
        return await ctx.send("❌ Geçersiz varlık adı.")

    user = get_user(ctx.author.id)
    sahip = user.get("yatirim", {}).get(varlik, 0)

    if sahip < miktar:
        return await ctx.send("❌ Yeterli varlığa sahip değilsin.")

    veri = economy_col.find_one({"_id": varlik})
    fiyat = veri["current_price"] if veri else varsayilan_varlikler[varlik]

    toplam_kazanc = fiyat * miktar

    collection.update_one(
        {"_id": str(ctx.author.id)},
        {
            "$inc": {
                "para": toplam_kazanc,
                f"yatirim.{varlik}": -miktar
            }
        }
    )

    await ctx.send(
        f"✅ {miktar} adet **{varlik}** sattın.\n💰 Kazanç: {formatla(toplam_kazanc)}"
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
    # Tüm sunuculardaki kullanıcı sayısı
    oyuncu_sayisi = sum(guild.member_count for guild in bot.guilds)

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
    view = View()
    invite_button = Button(
        label="Uygulamayı Ekle",
        url="https://discord.com/oauth2/authorize?client_id=1471843858101960776&permissions=8&scope=bot"
    )
    view.add_item(invite_button)
    await ctx.send("Botu sunucuna eklemek için aşağıdaki butona tıkla:", view=view)

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

@tasks.loop(minutes=10)
async def otomatik_gzenginler():

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

    # Büyükten küçüğe sırala
    sirali = sorted(liste, key=lambda x: x[1], reverse=True)[:10]

    embed = discord.Embed(
        title="🌍 Global En Zenginler Listesi",
        color=discord.Color.gold()
    )

    if not sirali:
        embed.description = "Henüz veri yok."
    else:
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

    # Eski mesajı bulup güncelle
    async for msg in kanal.history(limit=10):
        if msg.author == bot.user:
            await msg.edit(embed=embed)
            return

    # Eğer mesaj yoksa yeni at
    await kanal.send(embed=embed)

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

@tasks.loop(minutes=10)
async def enflasyon_gonder():

    kanal = await bot.fetch_channel(1474499745257881762)

    toplam = global_toplam_para()

    embed = discord.Embed(
        title="📈 Güncel Enflasyon",
        description=f"Toplam Dolaşımdaki EwoCoin:\n\n💸 **{toplam:,}**",
        color=discord.Color.red()
    )

    await kanal.send(embed=embed)

# ------------------- q!soygun -------------------
@bot.command()
@commands.cooldown(1, 500, commands.BucketType.user)
async def soygun(ctx, member: discord.Member):

    if member.bot:
        return await ctx.send("❌ Botu soyamazsın.")

    if member == ctx.author:
        return await ctx.send("❌ Kendini soyamazsın.")

    soyguncu = get_user(ctx.author.id)
    hedef = get_user(member.id)

    if soyguncu["para"] < 5000:
        return await ctx.send("❌ Soygun için en az 5.000 EwoCoin lazım!")

    if hedef["para"] < 10000:
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

    # Güvenlik clamp
    basari_orani = max(0.05, min(basari_orani, 0.95))
    calma_orani = max(0.05, min(calma_orani, 0.50))

    # --- Soygun Denemesi ---
    if random.random() < basari_orani:

        kazanilan = max(500, int(hedef["para"] * calma_orani))

        # Hedeften düş
        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"para": -kazanilan}}
        )

        # Soyguncuya ekle
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

    # --- Tek Kullanımlık Boost Düşürme ---
    update_dict = {}

    if silah_var:
        update_dict["envanter.Silah"] = -1

    if koruma_var:
        collection.update_one(
            {"_id": str(member.id)},
            {"$inc": {"envanter.Özel Koruma": -1}}
        )

    if update_dict:
        collection.update_one(
            {"_id": str(ctx.author.id)},
            {"$inc": update_dict}
        )

    await ctx.send(sonuc)

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

import asyncio
import time

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

# Sunucuya eklenme logu (ekleyen kişinin ismi eklendi)
@bot.event
async def on_guild_join(guild):
    kanal = bot.get_channel(EKLEME_LOG_KANAL)
    inviter_name = "Bilinmiyor"
    if guild.owner:
        inviter_name = guild.owner.name
    if kanal:
        embed = discord.Embed(
            title="🎉 EwoBot Sunucuya Eklendi!",
            color=discord.Color.green()
        )
        embed.add_field(name="Sunucu", value=guild.name)
        embed.add_field(name="Üye Sayısı", value=guild.member_count)
        embed.add_field(name="Ekleyen", value=inviter_name)
        embed.set_footer(text=f"Sunucu ID: {guild.id}")
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
# 🔥 EWO FULL ADMIN PANEL SYSTEM
# =====================================================

ADMIN_ID = 1271933410251772017
BAKIM_KANAL_ID = 1474489287859769656
EKONOMI_LOG_KANAL = 1474499591238848555

# =====================================================
# ANA KOMUT
# =====================================================

@bot.command()
async def adminpaneli(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ Bu komut sadece bota özeldir.")
    await ctx.send(embed=admin_main_embed(), view=AdminMainView())


def admin_main_embed():
    embed = discord.Embed(
        title="⚙️ EwoBot Admin Paneli",
        description=(
            "💰 Ekonomi & Para\n"
            "🔒 Kanal Kontrol\n"
            "🛠 Bakım Modu\n"
            "📢 Duyuru Sistemi"
        ),
        color=discord.Color.dark_blue()
    )
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
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

    @discord.ui.button(label="📢 Duyuru Sistemi", style=discord.ButtonStyle.success)
    async def duyuru(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="📢 Duyuru Sistemi", color=discord.Color.dark_blue()),
            view=DuyuruView()
        )

# =====================================================
# 💰 EKONOMİ VIEW (FAİZ + MAAŞ ÇALIŞIR)
# =====================================================

class EkonomiView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # 🔵 FAİZ YATIR
    @discord.ui.button(label="Faiz Yatır (%5)", style=discord.ButtonStyle.primary)
    async def faiz_yatir(self, interaction: discord.Interaction, button: discord.ui.Button):

        users = collection.find()

        for user in users:
            banka = user.get("banka", 0)
            faiz = int(banka * 0.05)

            collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {"banka": faiz}}
            )

        kanal = bot.get_channel(1475130412148723723)

        embed = discord.Embed(
            title="🏦 Faiz Ödemeleri Tamamlandı",
            description="Tüm banka hesaplarına %5 faiz eklenmiştir.",
            color=discord.Color.dark_blue()
        )

        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="EwoBot Finans Sistemi")

        if kanal:
            await kanal.send(embed=embed)

        await interaction.response.send_message("✅ Faiz yatırıldı.", ephemeral=True)

    # 🔵 MAAŞ YATIR
    @discord.ui.button(label="Maaş Yatır", style=discord.ButtonStyle.primary)
    async def maas_yatir(self, interaction: discord.Interaction, button: discord.ui.Button):

        users = collection.find()

        for user in users:
            meslek = user.get("meslek", "İşsiz")
            maas = meslekler.get(meslek, {}).get("maas", 0)

            collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {"banka": maas}}
            )

        kanal = bot.get_channel(1475130412148723723)

        embed = discord.Embed(
            title="💰 Maaş Ödemeleri Tamamlandı",
            description="Tüm kullanıcıların maaşları banka hesaplarına yatırılmıştır.",
            color=discord.Color.dark_blue()
        )

        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="EwoBot Finans Sistemi")

        if kanal:
            await kanal.send(embed=embed)

        await interaction.response.send_message("✅ Maaş yatırıldı.", ephemeral=True)

    # ==========================
    # EKONOMİ SIFIRLA
    # ==========================
    @discord.ui.button(label="Ekonomi Sıfırla", style=discord.ButtonStyle.danger, custom_id="ekonomi_sifirla")
    async def sifirla(self, interaction: discord.Interaction, button: discord.ui.Button):

        for varlik, fiyat in varsayilan_varlikler.items():
            economy_col.update_one(
                {"_id": varlik},
                {"$set": {"current_price": fiyat}},
                upsert=True
            )

        await interaction.response.send_message("💰 Ekonomi sıfırlandı.", ephemeral=True)

    # ==========================
    # EKONOMİ DEĞİŞTİR (RANDOM + LOG)
    # ==========================
    @discord.ui.button(label="Ekonomi Değiştir", style=discord.ButtonStyle.success, custom_id="ekonomi_degistir")
    async def degistir(self, interaction: discord.Interaction, button: discord.ui.Button):

        kanal = bot.get_channel(1474499591238848555)

        embed = discord.Embed(
            title="📊 EwoEkonomi Güncellendi!",
            color=discord.Color.dark_blue()
        )

        for varlik in varsayilan_varlikler.keys():
            data = economy_col.find_one({"_id": varlik})
            eski = data["current_price"]

            degisim = random.uniform(-0.20, 0.20)  # -%20 +%20
            yeni = int(eski * (1 + degisim))

            economy_col.update_one(
                {"_id": varlik},
                {"$set": {"current_price": yeni}}
            )

            emoji = "🟢" if yeni > eski else "🔴"

            embed.add_field(
                name=f"{emoji} {varlik}",
                value=f"Eski: {formatla(eski)} → Yeni: {formatla(yeni)}",
                inline=False
            )

        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="EwoBot Global Ekonomi Sistemi")

        if kanal:
            await kanal.send(embed=embed)

        await interaction.response.send_message("✅ Ekonomi değiştirildi.", ephemeral=True)

    # ==========================
    # GERİ
    # ==========================
    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary, custom_id="geri")
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
        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )
        await interaction.response.send_message("🔒 Kanal kilitlendi.", ephemeral=True)

    @discord.ui.button(label="Kitle Aç", style=discord.ButtonStyle.success)
    async def ac(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=True
        )
        await interaction.response.send_message("🔓 Kanal açıldı.", ephemeral=True)

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=admin_main_embed(), view=AdminMainView())

# =====================================================
# BAKIM SİSTEMİ
# =====================================================

@bot.check
async def global_bakim_kontrol(ctx):
    ayar = settings_col.find_one({"_id": "global"})
    bakim = ayar.get("bakim_modu", False) if ayar else False
    if bakim and ctx.author.id != ADMIN_ID:
        return False
    return True


class BakimView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bakım Başlat", style=discord.ButtonStyle.danger)
    async def baslat(self, interaction: discord.Interaction, button: discord.ui.Button):

        settings_col.update_one(
            {"_id": "global"},
            {"$set": {"bakim_modu": True}},
            upsert=True
        )

        kanal = bot.get_channel(BAKIM_KANAL_ID)

        embed = discord.Embed(
            title="🛠 EwoBot Bakım Modu",
            description="@everyone\nBot bakım moduna alınmıştır.\nKomutlar geçici olarak devre dışıdır.",
            color=discord.Color.dark_blue()
        )
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="EwoBot Sistem Bildirimi")

        if kanal:
            await kanal.send(embed=embed)

        await interaction.response.send_message("✅ Bakım başlatıldı.", ephemeral=True)

    @discord.ui.button(label="Bakım Bitir", style=discord.ButtonStyle.success)
    async def bitir(self, interaction: discord.Interaction, button: discord.ui.Button):

        settings_col.update_one(
            {"_id": "global"},
            {"$set": {"bakim_modu": False}},
            upsert=True
        )

        kanal = bot.get_channel(BAKIM_KANAL_ID)

        embed = discord.Embed(
            title="✅ EwoBot Bakım Tamamlandı",
            description="@everyone\nBakım modu kapatıldı.\nArtık herkes komutları kullanabilir.",
            color=discord.Color.dark_blue()
        )
        embed.set_thumbnail(url=bot.user.avatar.url)
        embed.set_footer(text="EwoBot Sistem Bildirimi")

        if kanal:
            await kanal.send(embed=embed)

        await interaction.response.send_message("✅ Bakım kapatıldı.", ephemeral=True)

    @discord.ui.button(label="Geri", style=discord.ButtonStyle.secondary)
    async def geri(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=admin_main_embed(), view=AdminMainView())

# ------------------- MARKET ANA KOMUT -------------------

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
            "🟤 Bronz Kasa → 100 - 1.000 EwoCoin\n"
            "⚪ Gümüş Kasa → 200 - 5.000 EwoCoin\n"
            "🟡 Altın Kasa → 400 - 10.000 EwoCoin\n"
            "💎 Elmas Kasa → 750 - 25.000 EwoCoin\n"
            "🌟 Premium Kasa → 1.000 - 50.000 EwoCoin\n"
            "🔥 EwoPlus Kasa → 5.000 - 100.000 EwoCoin\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🕶 **SOYGUN KATEGORİSİ**\n\n"
            "🔫 Silah → +%50 başarı & +%10 daha fazla çalma\n"
            "🛡 Özel Koruma → -%25 rakip başarı & -%10 çalma\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎣 **EKONOMİ KATEGORİSİ**\n\n"
            "🎣 Olta → Efsanevi balık boostu"
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
        description="Silah - 15000\nÖzel Koruma - 20000",
        color=discord.Color.red()
    )


def ekonomi_market_embed():
    return discord.Embed(
        title="🎣 Ekonomi Ürünleri",
        description="Olta - 1000",
        color=discord.Color.blue()
    )


# ------------------- KASA VIEW -------------------

class KasaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Bronz Kasa Al", style=discord.ButtonStyle.secondary)
    async def bronz(self, interaction, button):
        await satin_al(interaction, "Bronz Kasa")

    @discord.ui.button(label="Gümüş Kasa Al", style=discord.ButtonStyle.secondary)
    async def gumus(self, interaction, button):
        await satin_al(interaction, "Gümüş Kasa")

    @discord.ui.button(label="Altın Kasa Al", style=discord.ButtonStyle.secondary)
    async def altin(self, interaction, button):
        await satin_al(interaction, "Altın Kasa")

    @discord.ui.button(label="Elmas Kasa Al", style=discord.ButtonStyle.secondary)
    async def elmas(self, interaction, button):
        await satin_al(interaction, "Elmas Kasa")

    @discord.ui.button(label="Premium Kasa Al", style=discord.ButtonStyle.secondary)
    async def premium(self, interaction, button):
        await satin_al(interaction, "Premium Kasa")

    @discord.ui.button(label="EwoPlus Kasa Al", style=discord.ButtonStyle.secondary)
    async def ewoplus(self, interaction, button):
        await satin_al(interaction, "EwoPlus Kasa")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):
        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )


# ------------------- SOYGUN VIEW -------------------

class SoygunMarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Silah Al (15000)", style=discord.ButtonStyle.danger)
    async def silah(self, interaction, button):
        await satin_al(interaction, "Silah")

    @discord.ui.button(label="Özel Koruma Al (20000)", style=discord.ButtonStyle.primary)
    async def koruma(self, interaction, button):
        await satin_al(interaction, "Özel Koruma")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):
        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )


# ------------------- EKONOMİ VIEW -------------------

class EkonomiMarketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Olta Al (1000)", style=discord.ButtonStyle.success)
    async def olta(self, interaction, button):
        await satin_al(interaction, "Olta")

    @discord.ui.button(label="⬅️ Geri", style=discord.ButtonStyle.grey)
    async def geri(self, interaction, button):
        await interaction.response.edit_message(
            embed=market_ana_embed(),
            view=MarketMainView()
        )


# ------------------- SATIN AL FONKSİYONU -------------------

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
    envanter = user["envanter"]

    text = ""
    for urun, adet in envanter.items():
        if adet > 0:
            text += f"{urun}: {adet}\n"

    if text == "":
        text = "Envanter boş."

    embed = discord.Embed(
        title="🎒 Envanterin",
        description=text,
        color=discord.Color.dark_blue()
    )

    embed.set_thumbnail(url=ctx.author.avatar.url)

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

# ONNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNREADYYYYYYYYYYYYYYYYYY

@bot.event
async def on_ready():
    print(f"{bot.user} aktif!")

    bot.add_view(TicketPanelView())

    # Durum loop
    if not durum_degistir.is_running():
        print("Durum değiştir loop başlatıldı")
        durum_degistir.start()

    # Global zenginler loop
    if not otomatik_gzenginler.is_running():
        print("Global zenginler loop başlatıldı")
        otomatik_gzenginler.start()

    # Enflasyon loop
    if not enflasyon_gonder.is_running():
        print("Enflasyon loop başlatıldı")
        enflasyon_gonder.start()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"].startswith("ticket_cevap_"):
            user_id = int(interaction.data["custom_id"].split("_")[-1])
            await interaction.response.send_modal(TicketCevapModal(user_id))

keep_alive()
bot.run(os.getenv("TOKEN"))