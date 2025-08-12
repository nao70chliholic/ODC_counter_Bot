

import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime, time
from collections import Counter
import csv
import io
import typing

# --- 定数・設定 --- #

# .envファイルから環境変数を読み込む
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Botのインテントを設定
intents = discord.Intents.default()
intents.message_content = True

# Botオブジェクトを作成
bot = commands.Bot(command_prefix='!', intents=intents)


# --- ヘルパー関数 --- #

async def fetch_messages(channel: discord.TextChannel, keyword: str, after: datetime, before: datetime) -> list[discord.Message]:
    """指定された条件でメッセージを取得する"""
    found_messages = []
    async for message in channel.history(limit=None, after=after, before=before):
        if not message.author.bot and keyword in message.content:
            found_messages.append(message)
    return found_messages

def create_ranking_message(sorted_counts: list[tuple[str, int]], keyword: str, start_date: str, end_date: str) -> str:
    """ランキング表示用のメッセージを作成する"""
    response = f"**「{keyword}」検索結果ランキング** ({start_date} ~ {end_date})\n"
    response += "----------------------------------\n"
    for i, (user, count) in enumerate(sorted_counts):
        line = f"{i + 1}. {user}: {count}件\n"
        if len(response) + len(line) > 1900: # Discordのメッセージ長制限を考慮
            response += "（結果が多すぎるため、一部のみ表示しています）"
            break
        response += line
    return response

def create_log_csv_file(messages: list[discord.Message], keyword: str, start_date: str, end_date: str) -> discord.File:
    """メッセージの詳細ログを記録したCSVファイルを作成する"""
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerow(['User', 'Date', 'Time', 'Message']) # ヘッダー

    # 投稿者名、日付でソートして書き込み
    for message in sorted(messages, key=lambda m: (m.author.display_name, m.created_at)):
        csv_writer.writerow([
            message.author.display_name,
            message.created_at.strftime('%Y-%m-%d'),
            message.created_at.strftime('%H:%M:%S'),
            message.content
        ])
    csv_buffer.seek(0);

    filename = f"{keyword}_log_sorted_by_user_{start_date}_to_{end_date}.csv"
    return discord.File(fp=csv_buffer, filename=filename)


# --- Botイベント --- #

@bot.event
async def on_ready():
    """Botが起動したときに呼び出されるイベント"""
    print(f'{bot.user.name} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print('------')


# --- スラッシュコマンド --- #

@bot.tree.command(name="search_count", description="このチャンネルの指定期間内のキーワード出現回数を集計し、CSVで出力します。")
@app_commands.describe(
    keyword="検索するキーワード（例: ODC）",
    start_date="集計開始日 (YYYY-MM-DD)",
    end_date="集計終了日 (YYYY-MM-DD)"
)
async def search_count(interaction: discord.Interaction, keyword: str, start_date: str, end_date: str):
    """
    コマンドが実行されたチャンネルのメッセージを検索し、キーワードを含むメッセージを投稿者ごとにカウント＆詳細ログを出力するコマンド
    """
    await interaction.response.defer(ephemeral=True)

    try:
        # 日付文字列をdatetimeオブジェクトに変換
        try:
            after_time = datetime.strptime(start_date, '%Y-%m-%d')
            before_time = datetime.combine(datetime.strptime(end_date, '%Y-%m-%d'), time.max)
        except ValueError:
            await interaction.followup.send("エラー: 日付は「YYYY-MM-DD」の形式で指定してください。", ephemeral=True)
            return

        await interaction.followup.send(f"集計を開始します。チャンネル: {interaction.channel.mention}, 期間: {start_date} ~ {end_date}", ephemeral=True)

        # メッセージを取得
        messages = await fetch_messages(interaction.channel, keyword, after_time, before_time)

        if not messages:
            await interaction.followup.send(f"指定された期間内に、キーワード「{keyword}」を含むメッセージは見つかりませんでした。", ephemeral=True)
            return

        # ランキングを作成
        counts = Counter(msg.author.display_name for msg in messages)
        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ranking_message = create_ranking_message(sorted_counts, keyword, start_date, end_date)

        # CSVファイルを作成
        csv_file = create_log_csv_file(messages, keyword, start_date, end_date)
        
        # 結果を送信
        await interaction.followup.send(ranking_message, file=csv_file, ephemeral=True)

    except discord.Forbidden:
        await interaction.followup.send("エラー: Botにこのチャンネルの履歴を読む権限がありません。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)
        print(f"An error occurred in search_count: {e}")


# --- Bot実行 --- #

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("エラー: DISCORD_BOT_TOKENが.envファイルに設定されていません。")
