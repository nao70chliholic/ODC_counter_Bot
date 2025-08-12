import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from datetime import datetime, time
from collections import Counter
import csv
import io

# .envファイルから環境変数を読み込む
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Botのインテントを設定
intents = discord.Intents.default()
intents.message_content = True

# Botオブジェクトを作成
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    """Botが起動したときに呼び出されるイベント"""
    print(f'{bot.user.name} has connected to Discord!')
    try:
        # スラッシュコマンドをDiscordに同期
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print('------')

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
    # ephemeral=Trueにすることで、コマンドの結果が実行者のみに見えるようになる
    await interaction.response.defer(ephemeral=True)

    try:
        # コマンドが実行されたチャンネルを取得
        channel = interaction.channel

        # --- 引数の検証と変換 ---
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            await interaction.followup.send("エラー: 日付は「YYYY-MM-DD」の形式で指定してください。", ephemeral=True)
            return

        after_time = start_dt
        before_time = datetime.combine(end_dt, time.max)

        # --- メッセージの検索と集計 ---
        await interaction.followup.send(f"集計を開始します。チャンネル: {channel.mention}, 期間: {start_date} ~ {end_date}", ephemeral=True)

        found_messages = []
        async for message in channel.history(limit=None, after=after_time, before=before_time):
            if message.author.bot:
                continue
            if keyword in message.content:
                found_messages.append(message)

        if not found_messages:
            await interaction.followup.send(f"指定された期間内に、キーワード「{keyword}」を含むメッセージは見つかりませんでした。", ephemeral=True)
            return

        # --- ランキング集計 ---
        counts = Counter(msg.author.display_name for msg in found_messages)
        sorted_counts = sorted(counts.items(), key=lambda item: item[1], reverse=True)

        # --- ランキングメッセージの作成 ---
        response = f"**「{keyword}」検索結果ランキング** ({start_date} ~ {end_date})\n"
        response += "----------------------------------\n"
        for i, (user, count) in enumerate(sorted_counts):
            line = f"{i + 1}. {user}: {count}件\n"
            if len(response) + len(line) > 1900:
                response += "（結果が多すぎるため、一部のみ表示しています）"
                break
            response += line

        # --- 詳細ログCSVファイルの生成 (投稿者別、日付順) ---
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(['User', 'Date', 'Time', 'Message']) # ヘッダー
        
        # 投稿者名、日付でソート
        for message in sorted(found_messages, key=lambda m: (m.author.display_name, m.created_at)):
            csv_writer.writerow([
                message.author.display_name,
                message.created_at.strftime('%Y-%m-%d'),
                message.created_at.strftime('%H:%M:%S'),
                message.content
            ])
        csv_buffer.seek(0)

        csv_filename = f"{keyword}_log_sorted_by_user_{start_date}_to_{end_date}.csv"
        csv_file = discord.File(fp=csv_buffer, filename=csv_filename)
        
        # --- 結果の送信 (テキスト + CSV) ---
        await interaction.followup.send(response, file=csv_file, ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)
        print(f"An error occurred in search_count: {e}")

# Botを実行
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー: DISCORD_BOT_TOKENが.envファイルに設定されていません。")