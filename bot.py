import re
import os
import json
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# --- CẤU HÌNH ---
TOKEN = '8442263369:AAHIDb-6VkOk6XZJgIPzlPcKz6izek49G-w'
ADMIN_IDS = [507318519] 
GROUP_ID = -1002946689229 
DATA_FILE = 'bot_data.json'
AUTO_DELETE_TIME = 60 # Giây

# --- TỪ KHÓA BỎ QUA (Để tránh spam) ---
TU_KHOA_BO_QUA = [
    'đã nhận', 'nhận đủ', 'đủ usd', 'đủ tiền', 
    'đã bank', 'đã chuyển', 'check giúp', 'kiểm tra giúp',
    'done', 'xong rồi', 'uy tín', 'cảm ơn', 'thanks', 'ok', 'oke'
]

NOI_DUNG_CK = """
✅ **NGÂN HÀNG:** ACB
✅ **CHỦ TÀI KHOẢN:** HO VAN LOI
✅ **SỐ TÀI KHOẢN:** `734838`
*(STK chỉ có 6 số - Mọi người lưu ý kỹ)*
"""

# --- QUẢN LÝ DỮ LIỆU ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {"rate": 27.0}

def save_data(rate):
    with open(DATA_FILE, 'w') as f:
        json.dump({"rate": rate}, f)

bot_data = load_data()
current_usd_rate = bot_data["rate"]

# --- SERVER KEEP ALIVE ---
app_flask = Flask('')
@app_flask.route('/')
def home(): return "Bot OK"
def run_http(): app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive(): t = Thread(target=run_http); t.start()

# --- HELPER: XÓA TIN NHẮN ---
async def delete_later(context, chat_id, message_id, delay=60):
    if delay <= 0: return
    await asyncio.sleep(delay)
    try: await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except: pass

# --- LOGIC BOT ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot đang hoạt động! Nhớ tắt Group Privacy để bot đọc được tin nhắn.")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_usd_rate
    if update.effective_user.id not in ADMIN_IDS: return

    try:
        if not context.args:
            await update.message.reply_text(f"ℹ️ Giá hiện tại: {current_usd_rate}")
            return
        new_rate = float(context.args[0].replace(',', '.'))
        if new_rate > 1000: new_rate /= 1000
        current_usd_rate = new_rate
        save_data(new_rate)
        await update.message.reply_text(f"✅ Đã set giá: {new_rate}")
    except:
        await update.message.reply_text("⚠️ Lỗi nhập liệu.")

# --- TÍNH NĂNG /CHOT (MỚI BỔ SUNG) ---
async def chot_deal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Xử lý lệnh: /chot 9000 email@gmail.com
    """
    try:
        if not context.args:
            await update.message.reply_text("⚠️ Sai cú pháp! Dùng: `/chot 1000 email...`", parse_mode='Markdown')
            return

        # Lấy số lượng từ tham số đầu tiên
        amount_str = context.args[0].replace(',', '').replace('.', '')
        amount = float(amount_str)
        
        # Lấy thông tin ghi chú (email, v.v.)
        note = " ".join(context.args[1:]) if len(context.args) > 1 else "Không có ghi chú"
        
        # Tính tiền
        total_vnd = amount * current_usd_rate * 1000
        formatted_vnd = "{:,.0f}".format(total_vnd).replace(',', '.')
        formatted_usd = "{:,.0f}".format(amount).replace(',', '.')
        
        # Lấy thời gian hiện tại
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_name = update.effective_user.first_name

        msg = (
            f"✅ **ĐÃ GHI SỔ THÀNH CÔNG**\n"
            f"📅 Ngày: {now}\n"
            f"👤 Khách: {user_name}\n"
            f"📧 Note: {note}\n"
            f"💵 Số tiền: **{formatted_usd} USD**\n"
            f"💰 Thành tiền: **{formatted_vnd} VNĐ**"
        )
        
        # Gửi tin nhắn xác nhận
        await update.message.reply_text(msg, parse_mode='Markdown')

    except ValueError:
        await update.message.reply_text("⚠️ Số lượng không hợp lệ.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    text = update.message.text.lower()
    
    # 1. Bỏ qua tin nhắn trong nhóm nếu không liên quan (để tránh spam log)
    # Nếu tin nhắn quá dài và không có số, bỏ qua
    if len(text) > 50 and not any(char.isdigit() for char in text):
        return

    # 2. Bỏ qua từ khóa blacklist
    if any(tk in text for tk in TU_KHOA_BO_QUA): return

    # 3. Logic bắt số (1000, 500, 10.5)
    # Regex: Bắt số đứng riêng lẻ hoặc kèm ký tự $
    match = re.search(r'\b(\d+[\.,]?\d*)\b', text)
    
    keywords = ['giá', 'rate', 'usd', 'đô', 'check', 'bn']
    has_keyword = any(kw in text for kw in keywords)
    
    is_pure_number = False
    if match:
        # Kiểm tra xem tin nhắn có phải chỉ toàn là số không (ví dụ: "500")
        clean = text.replace(',', '').replace('.', '').replace('$', '').strip()
        if clean.isdigit(): is_pure_number = True

    # QUY TẮC TRẢ LỜI:
    # - Nếu là số trần (vd: "500") -> Trả lời
    # - Nếu có từ khóa + số (vd: "giá 500") -> Trả lời
    # - Nếu chỉ hỏi "giá" không có số -> Trả lời báo giá
    
    if match and (is_pure_number or has_keyword):
        amount = float(match.group(1).replace(',', '.'))
        total = amount * current_usd_rate * 1000
        
        f_vnd = "{:,.0f}".format(total).replace(',', '.')
        f_usd = "{:,.2f}".format(amount).rstrip('0').rstrip('.').replace('.', ',')
        rate_show = "{:,.3f}".format(current_usd_rate).rstrip('0').rstrip('.')

        reply = (
            f"💵 **BÁO GIÁ NHANH:**\n"
            f"🔸 {f_usd} $ x {rate_show} = **{f_vnd} VNĐ**\n"
            f"------------------\n"
            f"{NOI_DUNG_CK}"
        )
        
        # Gửi ảnh QR nếu có, không thì gửi text
        script_dir = os.path.dirname(os.path.abspath(__file__))
        photo_path = os.path.join(script_dir, 'qr.jpg')
        try:
            if os.path.exists(photo_path):
                sent = await context.bot.send_photo(update.message.chat_id, photo=open(photo_path, 'rb'), caption=reply, parse_mode='Markdown')
            else:
                sent = await update.message.reply_text(reply, parse_mode='Markdown')
            
            # Auto xóa
            if AUTO_DELETE_TIME > 0:
                asyncio.create_task(delete_later(context, sent.chat_id, sent.message_id, AUTO_DELETE_TIME))
        except: pass

    elif has_keyword:
        # Chỉ hỏi giá
        rate_show = "{:,.3f}".format(current_usd_rate).rstrip('0').rstrip('.')
        await update.message.reply_text(f"📈 Tỷ giá hiện tại: **{rate_show}**", parse_mode='Markdown')

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("gia", set_rate))
    app.add_handler(CommandHandler("chot", chot_deal)) # Đã thêm lệnh chốt
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
