import disnake
from disnake.ext import commands
import json, os, datetime

intents = disnake.Intents.all()
bot = commands.Bot(command_prefix="-", intents=intents)

BANK_FILE = "bank.json"
VIOLATION_FILE = "violations.json"
SALARY_AMOUNT = 500

# =======================
# DATABASE
# =======================
def load(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# =======================
# USER (🎁 1000)
# =======================
def get_user(gid, uid):
    db = load(BANK_FILE)
    gid, uid = str(gid), str(uid)

    if gid not in db:
        db[gid] = {}

    if uid not in db[gid]:
        db[gid][uid] = {"cash": 1000, "bank": 0, "loan": 0}
        save(BANK_FILE, db)

    # لو المستخدم قديم وما عنده loan
    if "loan" not in db[gid][uid]:
        db[gid][uid]["loan"] = 0
        save(BANK_FILE, db)

    return db[gid][uid]

def update_user(gid, uid, data):
    db = load(BANK_FILE)
    gid, uid = str(gid), str(uid)

    if gid not in db:
        db[gid] = {}

    db[gid][uid] = data
    save(BANK_FILE, db)

# =======================
# VIOLATIONS
# =======================
VIOLATIONS = [
    ("زره", 500),
    ("قطع اشاره", 3000),
    ("عكس سير متعمد", "منع يومين"),
    ("سحب جلنط متقصد", 1000),
    ("سرعه 75-80", "منع يومين"),
    ("سرعه 81-90", "منع 3 ايام"),
    ("سرعه 90+", "منع 5 ايام"),
    ("تجاوز سيارات", 1000),
    ("هروب من عسكري", "باند"),
    ("تطلع الرصيف", 500),
    ("عدم وجود لوحه", 3000),
    ("التفحيط", 4500),
    ("سيارة سبورت بدون تصريح", 3000),
    ("تديور خط اصفر", 1000),
    ("عدم تشغيل اضواء", 500),
    ("لوحه مميزه بدون تصريح", 3000),
    ("صدم اقماع", 5000),
]

# =======================
# SELECT MENU
# =======================
class ViolationSelect(disnake.ui.Select):
    def __init__(self, member, image):
        options = [disnake.SelectOption(label=v[0], description=str(v[1])) for v in VIOLATIONS]
        super().__init__(placeholder="اختر المخالفة...", options=options)
        self.member = member
        self.image = image

    async def callback(self, inter):
        db = load(VIOLATION_FILE)
        gid = str(inter.guild.id)
        uid = str(self.member.id)

        if gid not in db:
            db[gid] = {}
        if uid not in db[gid]:
            db[gid][uid] = []

        selected = self.values[0]
        fine = next(v[1] for v in VIOLATIONS if v[0] == selected)

        db[gid][uid].append({"type": selected, "fine": fine})
        save(VIOLATION_FILE, db)

        embed = disnake.Embed(title="🚨 تم تسجيل مخالفة", color=0xff0000)
        embed.add_field(name="👤 المواطن", value=self.member.mention)
        embed.add_field(name="📄 المخالفة", value=selected)
        embed.add_field(name="💰 العقوبة", value=str(fine))

        if self.image:
            embed.set_image(url=self.image)

        await inter.message.delete()
        await inter.channel.send(embed=embed)

class ViolationView(disnake.ui.View):
    def __init__(self, member, image):
        super().__init__()
        self.add_item(ViolationSelect(member, image))

# =======================
# مخالفة
# =======================
@bot.command(name="مخالفة")
async def violation(ctx, member: disnake.Member):
    image = None
    if ctx.message.attachments:
        image = ctx.message.attachments[0].url

    embed = disnake.Embed(title="🚓 نظام المخالفات")
    if image:
        embed.set_image(url=image)

    await ctx.send(embed=embed, view=ViolationView(member, image))

# =======================
# تسديد مخالفات
# =======================
@bot.command(name="تسديد")
async def pay(ctx):
    db = load(VIOLATION_FILE)
    gid = str(ctx.guild.id)
    uid = str(ctx.author.id)

    if gid not in db or uid not in db[gid] or not db[gid][uid]:
        return await ctx.send("❌ ما عندك مخالفات")

    total = sum(v["fine"] for v in db[gid][uid] if isinstance(v["fine"], int))
    user = get_user(ctx.guild.id, ctx.author.id)

    if user["bank"] < total:
        return await ctx.send("❌ البنك ما يكفي")

    user["bank"] -= total
    update_user(ctx.guild.id, ctx.author.id, user)

    db[gid][uid] = []
    save(VIOLATION_FILE, db)

    await ctx.send(f"✅ تم دفع {total}")

# =======================
# رصيد
# =======================
@bot.command(name="رصيد")
async def balance(ctx, member: disnake.Member=None):
    if not member:
        member = ctx.author

    data = get_user(ctx.guild.id, member.id)

    embed = disnake.Embed(
        title=f"🏦 مصرف الراجحي | {member.display_name}",
        color=0x2b2d31
    )

    embed.add_field(name="💵 الكاش", value=data["cash"])
    embed.add_field(name="🏦 البنك", value=data["bank"])
    embed.add_field(name="📌 القرض", value=data.get("loan", 0))
    embed.add_field(name="📊 المجموع", value=data["cash"] + data["bank"])

    embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)

# =======================
# تحويل / إيداع / سحب
# =======================
@bot.command(name="تحويل")
async def transfer(ctx, member: disnake.Member, amount:int):
    user = get_user(ctx.guild.id, ctx.author.id)
    target = get_user(ctx.guild.id, member.id)

    if user["cash"] < amount:
        return await ctx.send("❌ ما عندك كاش")

    user["cash"] -= amount
    target["cash"] += amount

    update_user(ctx.guild.id, ctx.author.id, user)
    update_user(ctx.guild.id, member.id, target)

    await ctx.send("✅ تم التحويل")

@bot.command(name="إيداع")
async def deposit(ctx, amount:int):
    user = get_user(ctx.guild.id, ctx.author.id)

    if user["cash"] < amount:
        return await ctx.send("❌ ما عندك كاش")

    user["cash"] -= amount
    user["bank"] += amount

    update_user(ctx.guild.id, ctx.author.id, user)

    await ctx.send("🏦 تم الإيداع")

@bot.command(name="سحب")
async def withdraw(ctx, amount:int):
    user = get_user(ctx.guild.id, ctx.author.id)

    if user["bank"] < amount:
        return await ctx.send("❌ ما عندك بالبنك")

    user["bank"] -= amount
    user["cash"] += amount

    update_user(ctx.guild.id, ctx.author.id, user)

    await ctx.send("💸 تم السحب")

# =======================
# قرض / سداد قرض
# =======================
@bot.command(name="قرض")
async def loan(ctx, amount:int):
    user = get_user(ctx.guild.id, ctx.author.id)

    if user["loan"] > 0:
        return await ctx.send("❌ عندك قرض قائم، سدده أولاً")

    if amount <= 0:
        return await ctx.send("❌ المبلغ غير صحيح")

    if amount > 10000:
        return await ctx.send("❌ الحد الأقصى للقرض هو 10000")

    user["bank"] += amount
    user["loan"] = amount

    update_user(ctx.guild.id, ctx.author.id, user)

    await ctx.send(f"🏦 تم منحك قرض بقيمة {amount}")

@bot.command(name="تسديد-قرض")
async def repay_loan(ctx):
    user = get_user(ctx.guild.id, ctx.author.id)

    if user["loan"] <= 0:
        return await ctx.send("✅ ما عندك قرض")

    if user["bank"] < user["loan"]:
        return await ctx.send("❌ رصيد البنك لا يكفي")

    amount = user["loan"]
    user["bank"] -= amount
    user["loan"] = 0

    update_user(ctx.guild.id, ctx.author.id, user)

    await ctx.send(f"✅ تم تسديد القرض ({amount})")

# =======================
# الرواتب
# =======================
@bot.command(name="الرواتب")
@commands.has_permissions(administrator=True)
async def salaries(ctx):
    now = datetime.datetime.now()
    days_ahead = 4 - now.weekday()
    if days_ahead <= 0:
        days_ahead += 7

    next_salary = now + datetime.timedelta(days=days_ahead)
    next_salary = next_salary.replace(hour=23, minute=0, second=0)

    diff = next_salary - now
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds // 60) % 60

    embed = disnake.Embed(color=0x2b2d31)
    embed.description = f"🕒 حالة الرواتب\n\n📅 كل جمعة 11 مساءً\n\n⏳ باقي:\n{days} يوم و {hours} ساعة و {minutes} دقيقة"

    await ctx.send(embed=embed)

@bot.command(name="صرف-رواتب")
@commands.has_permissions(administrator=True)
async def give_salaries(ctx):
    db = load(BANK_FILE)
    gid = str(ctx.guild.id)

    if gid not in db:
        return await ctx.send("❌ ما فيه بيانات")

    count = 0
    for uid in db[gid]:
        user = get_user(ctx.guild.id, uid)
        user["bank"] += SALARY_AMOUNT
        update_user(ctx.guild.id, uid, user)
        count += 1

    embed = disnake.Embed(
        title="💸 تم صرف الرواتب",
        description=f"تم صرف الرواتب لـ {count} موظف",
        color=disnake.Color.green()
    )

    await ctx.send(embed=embed)

# =======================
# إعطاء
# =======================
@bot.command(name="إعطاء")
@commands.has_permissions(administrator=True)
async def give(ctx, member: disnake.Member, amount:int):
    user = get_user(ctx.guild.id, member.id)
    user["cash"] += amount
    update_user(ctx.guild.id, member.id, user)

    await ctx.send("💰 تم إعطاء فلوس")

# =======================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("TOKEN"))
