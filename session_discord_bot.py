from core.auth import Authentication
import asyncio
from datetime import datetime, timedelta, tzinfo, timezone
import discord
from discord.ext import tasks
from core.google_sheets import GoogleSheets

intents = discord.Intents.default()
intents.members = True

auth = Authentication()
client : discord.client.Client = discord.Client(intents=intents)
guild = None
general_channel = None

sessions_sheet = GoogleSheets()
sessions_sheet.load_sheet("Sessions")


sessions = [(datetime.fromisoformat(s["DateTime Start"].replace('Z', '+00:00')) - timedelta(minutes=5), datetime.fromisoformat(s["DateTime End"].replace('Z', '+00:00')), s) for s in sessions_sheet.data]
session_id_to_channel = {}

sheet_tracks = GoogleSheets()
sheet_tracks.load_sheet("Tracks")
tracks_dict = dict()
for t in sheet_tracks.data:
    tracks_dict[t["Track"]] = t

    
last_tick = datetime.now(timezone.utc) - timedelta(minutes=25.0)

@client.event
async def on_ready():
    global guild
    global session_id_to_channel
    global general_channel
    for g in client.guilds:
        print(g)
        print(g.id)
        if g.id == auth.discord["discord_server_id"]:
            guild = g
            break
    if guild is None:
        print("Guild not found")
        return
    for ch in guild.text_channels:
        if ch.name == "general":
            general_channel = ch
            break
    #client.loop.create_task(post_session_info())
    for s in sessions_sheet.data:
        sid = s["Session ID"]
        if(len(sid.strip()) == 0):
            continue
        tr = s["Track"]
        if tr is None or tr not in tracks_dict:
            continue
        track = tracks_dict[tr]
        ch_id_s = track["Discord Channel ID"].strip()
        if(len(ch_id_s) == 0):
            continue
        ch_id = int(ch_id_s)
        for ch in guild.text_channels:
            if ch.id == ch_id:
                session_id_to_channel[sid] = ch
                print(f"Found channel {ch.name} for session {sid}, start at {datetime.fromisoformat(s['DateTime Start'].replace('Z', '+00:00'))}")
                break


    print("Bot ready.")


@client.event
async def on_message(msg):
    if(msg.author == client.user):
        return

@tasks.loop(minutes=1.0)
async def post_session_info():
    global guild
    global session_id_to_channel
    global sessions
    global last_tick
    #print("tick")
    if not guild:
        return
    dt = datetime.now(timezone.utc)
    
    #print(f"{dt} tick")
    for start, end, session in sessions:
        if last_tick < start and dt >= start and dt < end:
            sid = session["Session ID"].strip()
            print(f"{dt} session {sid} is happening now")
            if len(sid) == 0 or sid not in session_id_to_channel:
                continue
            ch = session_id_to_channel[sid]
            title = session["Session Title"]
            track = session["Track"]
            if len(track) == 0 or track == "various" or track == "none":
                continue
            print(f"{dt} sending message")
            await ch.send(content=f"The session **{title}** in this track is going to start in just a few minutes.\r\nCheck the session overview on our content website: https://content.ieeevis.org/year/2023/session_{sid}.html\r\nPlease use this channel for fruitful exchanges, but note that session chairs will not pick up questions on Discord for Q+A.")
    last_tick = dt

#asyncio.run(post_session_info())
post_session_info.start()
client.run(auth.discord["bot_token"])