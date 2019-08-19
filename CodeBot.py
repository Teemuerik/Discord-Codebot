# -*- coding: utf-8 -*-

import asyncio
import discord
import json
import os
import re

from discord.ext import commands
from discord.utils import get

TOKEN = "NjEwNzkwMDk0NjA5MDU1Nzc3.XVKZ2g.QPtPHeZ4mAm1vT9Y3EVqzWQcsGw"

MAX_MESSAGE_LEN = 2000

bot = commands.Bot(command_prefix="$")

role_msg_content = "Valitse rooleja:"

class ServerConfig:
    role_reactions = {}

    async def to_json(self):
        data = {}
        data["role_reactions"] = self.role_reactions
        return data
    
    @staticmethod
    async def from_json(data):
        config = ServerConfig()
        config.role_reactions = data["role_reactions"]
        return config

async def get_config(guild_id) -> ServerConfig:
    config = ServerConfig()
    fn = str(guild_id) + ".json"
    if os.path.exists(fn):
        with open(fn, "r") as f:
            config = await ServerConfig.from_json(json.load(f))
    return config

async def set_config(config, guild_id):
    with open(str(guild_id) + ".json", "w") as f:
        json.dump(await config.to_json(), f)

# Role selector

@bot.command(name="role_message", pass_context=True)
@commands.has_permissions(administrator=True)
async def send_role_message(ctx):
    await ctx.message.delete()
    await ctx.send(role_msg_content)

async def add_role_reaction(member: discord.Member, channel: discord.TextChannel, reaction, guild: discord.Guild):
    check = lambda m: m.author == member
    msgs = []
    while True:
        msgs.append(await channel.send(f"Kirjoita roolin nimi reaktiolle :{reaction}:"))
        msg: discord.Message = await bot.wait_for('message', check=check)
        msgs.append(msg)
        if msg.content in [r.name for r in guild.roles]:
            print("Role found in guild roles...")
            for m in msgs:
                await m.delete()
            break
        else:
            print(f"Role \"{msg.content}\" not found.")
            msgs.append(await channel.send(f"Roolia \"{msg.content}\" ei ole tällä palvelimella."))
    print("Adding role to config...")
    config = await get_config(guild.id)
    config.role_reactions[reaction] = get(guild.roles, name=msg.content).id
    await set_config(config, guild.id)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    config = await get_config(payload.guild_id)
    channel: discord.TextChannel = bot.get_channel(payload.channel_id)
    user: discord.User = bot.get_user(payload.user_id)
    member: discord.Member = [m for m in channel.members if m.discriminator == user.discriminator][0]
    if payload.emoji.name not in config.role_reactions.keys():
        if member.guild_permissions.administrator:
            print("Prompting role add...")
            await add_role_reaction(member, channel, payload.emoji.name, bot.get_guild(payload.guild_id))
            return
        else:
            print("User can't add reactions, removing reaction...")
            return
    msg: discord.Message = await channel.fetch_message(payload.message_id)
    if msg.content == role_msg_content:
        role: discord.Role = get(member.guild.roles, id=config.role_reactions[payload.emoji.name])
        print(f"Adding role \"{role.name}\" to member \"{member.display_name}#{member.discriminator}\"")
        await member.add_roles(role)

@bot.event
async def on_raw_reaction_remove(payload):
    config = await get_config(payload.guild_id)
    channel: discord.TextChannel = bot.get_channel(payload.channel_id)
    user: discord.User = bot.get_user(payload.user_id)
    member: discord.Member = [m for m in channel.members if m.discriminator == user.discriminator][0]
    msg: discord.Message = await channel.fetch_message(payload.message_id)
    if msg.content == role_msg_content:
        role: discord.Role = get(member.guild.roles, id=config.role_reactions[payload.emoji.name])
        print(f"Removing role \"{role.name}\" from member \"{member.display_name}#{member.discriminator}\"")
        await member.remove_roles(role)

@bot.event
async def on_member_join(member: discord.Member):
    role: discord.Role = get(member.guild.roles, name="Code Monkey")
    print(f"Adding default role to member \"{member.display_name}#{member.discriminator}\"")
    await member.add_roles(role)

# Code file sender

def get_file_settings():
    with open("file_settings.json", "r") as f:
        return json.load(f)

def get_ext_settings(ext):
    settings = get_file_settings()
    if ext not in settings.keys():
        return settings["other"]
    return settings[ext]

def split_string_at(string, *indices):
    if len(indices) == 0:
        return [string]
    index_list = list(indices)
    if index_list[0] != 0:
        index_list.insert(0, 0)
    index_list.append(None)
    parts = [string[index_list[i]:index_list[i+1]] for i in range(len(index_list)-1)]
    return parts

def get_split_messages(file_content: str, ext):
    file_content.replace("    ", "\t")
    if len(file_content.rstrip()) <= MAX_MESSAGE_LEN:
        return file_content
    settings = get_ext_settings(ext)
    split_re = settings["message_split_regex"]
    split_i = settings["split_index"]
    
    positions = []
    max_priority = 0
    if "priority" not in split_re:
        # Get RegEx match positions.
        regex = re.compile(split_re)
        matches = regex.findall(file_content)
        for match in matches:
            if split_i < 0:
                positions.append((0, match.endpos + split_i + 1))
            else:
                positions.append((0, match.pos + split_i))
    else:
        curr_priority = 0
        while True:
            # Get RegEx match positions.
            regex = re.compile(split_re.replace("priority", str(curr_priority)))
            matches = regex.findall(file_content)
            if len(matches) == 0:
                max_priority = curr_priority - 1
                break
            for match in matches:
                if split_i < 0:
                    positions.append((curr_priority, match.endpos + split_i + 1))
                else:
                    positions.append((curr_priority, match.pos + split_i))

    # Set split positions to the start of the line.
    new_positions = []
    for pos in positions:
        while pos[1] != 0:
            pos[1] -= 1
            if file_content[pos[1]] == '\n':
                pos[1] += 1
                new_positions.append(pos)
                break
    all_parts = split_string_at(file_content, *[np[1] for np in new_positions])
    if len(all_parts) > 1:
        split_parts = [(0, all_parts[0])].extend(zip([np[0] for np in new_positions], all_parts[1:]))
    else:
        split_parts = [(0, all_parts[0])]

    # Split parts longer than the max length.
    parts = []
    for p in split_parts:
        while len(p[1].rstrip()) > MAX_MESSAGE_LEN:
            for x in range(MAX_MESSAGE_LEN):
                i = MAX_MESSAGE_LEN - x
                if p[1][i] == '\n':
                    p_priority = p[0]
                    p_split, p = split_string_at(p[1], i)
                    parts.append((p_priority, p_split))
        parts.append(p)
    
    # Join parts shorter than the max length.
    grouped_parts = []
    new_part = (0, "")
    for rpriority in range(max_priority + 1):
        priority = max_priority - rpriority
        for p in parts:
            if new_part == (0, ""):
                new_part = (priority - 1, p[1])
            if p[0] == priority:
                if len(new_part[1]) + len(p[1]) < MAX_MESSAGE_LEN:
                    new_part = (priority - 1, ''.join([new_part[1], p[1]]))
                elif len(new_part[1]) + len(p[1].rstrip()):
                    new_part = (priority - 1, ''.join([new_part[1], p[1].rstrip()]))
                else:
                    grouped_parts.append(new_part)
                    new_part = (0, "")
            else:
                grouped_parts.append(new_part)
                new_part = (0, "")
    
    # Return final messages.
    return [p[1].rstrip() for p in grouped_parts]

@bot.command(name="code", pass_context=True)
async def send_code_file(ctx):
    if len(ctx.message.attachments) == 0:
        msg = await ctx.send("Liitä viestiin tiedosto jonka haluat lähettää.\n(Viesti poistetaan automaattisesti.)")
        await asyncio.sleep(10)
        await ctx.message.delete()
        await msg.delete()
        return
    attachment: discord.Attachment = ctx.message.attachments[0]
    file_bytes: bytes = await attachment.read()
    try:
        content = file_bytes.decode()
    except UnicodeDecodeError:
        msg = await ctx.send("Liitetiedostoa ei voitu lukea.\n(Viesti poistetaan automaattisesti.)")
        await asyncio.sleep(10)
        await ctx.message.delete()
        await msg.delete()
        return
    filename = attachment.filename
    ext = filename.split(".")[1]
    messages = get_split_messages(content, ext)
    await ctx.send(f"{ctx.user.mention} lähetti tiedoston \"{filename}\".")
    for message in messages:
        await ctx.send(f"```{ext}\n{message}```")

bot.run(TOKEN)