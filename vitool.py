import requests
import json
import time
import os
import sys
import threading
import re # Import modul regex untuk validasi email
import webbrowser # Import modul webbrowser untuk membuka link

# --- KONFIGURASI ---
# Ganti URL ini jika Anda memiliki endpoint callback untuk menerima status transaksi.
# Jika tidak, Anda bisa membiarkannya, tetapi Anda harus memeriksa status secara manual.
URL_CALLBACK_ANDA = "https://example.com/callback" 

# --- Kelas untuk Warna Teks (Palet Modern & Mewah) ---
class Colors:
    # Menggunakan ANSI 256-color codes untuk palet yang lebih kaya
    HEADER = '\033[38;5;27m'  # Deep Blue (for main headers)
    ACCENT = '\033[38;5;129m' # Medium Purple (for secondary accents/titles)
    PRIMARY = '\033[38;5;39m'  # Vibrant Blue (for general info/options)
    SUCCESS = '\033[38;5;28m' # Emerald Green (for success messages)
    WARNING = '\033[38;5;214m' # Golden Orange (for warnings/prompts)
    FAIL = '\033[38;5;196m'    # Bright Red (for error messages)
    INFO = '\033[38;5;247m'    # Light Gray (for subtle info)
    ENDC = '\033[0m'           # Reset to default color
    BOLD = '\033[1m'           # Bold text
    UNDERLINE = '\033[4m'      # Underline text

# --- Variabel Global untuk Sesi & Animasi ---
sesi_login = {} # Simpan access_token di sini: { 'no_hp': 'access_token' }
FILE_KREDENSIAL = "kredensial.json"
FILE_SESI = "sesi_login.json"
is_loading = False

# --- Fungsi Animasi Loading ---
def loading_animation():
    """Menampilkan animasi spinner saat proses loading dengan warna yang lebih menarik."""
    global is_loading
    spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'] # More modern spinner characters
    i = 0
    while is_loading:
        sys.stdout.write(f"\r{Colors.ACCENT}{Colors.BOLD}Memproses... {spinner[i % len(spinner)]}{Colors.ENDC}")
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write('\r' + ' ' * 30 + '\r') # Membersihkan baris
    sys.stdout.flush()

# --- Fungsi untuk Mengelola Kredensial & Sesi ---
def simpan_kredensial(email, password, api_key):
    """Menyimpan kredensial API ke file JSON."""
    kredensial = {"email": email, "password": password, "api_key": api_key}
    with open(FILE_KREDENSIAL, 'w') as f:
        json.dump(kredensial, f)
    print(f"{Colors.SUCCESS}Kredensial telah disimpan dengan aman.{Colors.ENDC}")

def muat_kredensial():
    """Memuat kredensial API dari file JSON jika ada."""
    if os.path.exists(FILE_KREDENSIAL):
        with open(FILE_KREDENSIAL, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return None
    return None

def simpan_sesi(sesi_data):
    """Menyimpan sesi login OTP ke file JSON."""
    with open(FILE_SESI, 'w') as f:
        json.dump(sesi_data, f)

def muat_sesi():
    """Memuat sesi login OTP dari file JSON jika ada."""
    if os.path.exists(FILE_SESI):
        with open(FILE_SESI, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

# --- Fungsi Pembantu ---
def format_phone_number(no_hp):
    """Memformat nomor telepon dari 08... menjadi 62..."""
    if no_hp.startswith('0'):
        return '62' + no_hp[1:]
    return no_hp

def validate_email(email):
    """Memvalidasi format email menggunakan regex."""
    # Regex sederhana untuk validasi email
    if re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return True
    return False

def handle_api_error(func):
    """Decorator untuk menangani error umum saat melakukan panggilan API."""
    def wrapper(*args, **kwargs):
        global is_loading
        is_loading = True
        loader_thread = threading.Thread(target=loading_animation)
        loader_thread.start()
        
        try:
            # Panggil fungsi asli dengan argumen yang diberikan
            response = func(*args, **kwargs)
            return response
        except Exception as e:
            # Jika terjadi exception, lempar kembali untuk ditangani oleh blok di bawah
            raise e
        finally:
            # Pastikan animasi berhenti apa pun yang terjadi
            is_loading = False
            loader_thread.join()

    def inner_wrapper(*args, **kwargs):
        try:
            return wrapper(*args, **kwargs)
        except requests.exceptions.HTTPError as http_err:
            error_message = f"{Colors.FAIL}Error HTTP: {http_err}. Pastikan kredensial Anda benar.{Colors.ENDC}"
            print(error_message)
            try:
                response = http_err.response
                error_data = response.json()
                message = error_data.get("message")
                if message is None:
                    message = f"Respons error tidak standar: {json.dumps(error_data)}"
                print(f"{Colors.FAIL}Pesan dari server: {message}{Colors.ENDC}")
                return {"status": False, "message": message, "data": error_data.get("data")}
            except json.JSONDecodeError:
                print(f"{Colors.FAIL}Gagal menguraikan respons error. Respons mentah: {response.text}{Colors.ENDC}")
                return {"status": False, "message": str(http_err)}
        except requests.exceptions.ConnectionError as conn_err:
            error_message = f"{Colors.FAIL}Error Koneksi: {conn_err}. Periksa koneksi internet Anda.{Colors.ENDC}"
            print(error_message)
            return {"status": False, "message": str(conn_err)}
        except requests.exceptions.Timeout as timeout_err:
            error_message = f"{Colors.FAIL}Error Timeout: {timeout_err}. Permintaan terlalu lama.{Colors.ENDC}"
            print(error_message)
            return {"status": False, "message": str(timeout_err)}
        except requests.exceptions.RequestException as req_err:
            error_message = f"{Colors.FAIL}Terjadi kesalahan: {req_err}{Colors.ENDC}"
            print(error_message)
            return {"status": False, "message": str(req_err)}
        except json.JSONDecodeError:
            error_message = f"{Colors.FAIL}Error penguraian JSON. Respons tidak valid dari server.{Colors.ENDC}"
            print(error_message)
            return {"status": False, "message": "Respons tidak valid dari server."}
    return inner_wrapper


@handle_api_error
def make_get_request(url, params, auth, timeout=30):
    """Membuat permintaan GET ke API."""
    response = requests.get(url, params=params, auth=auth, timeout=timeout)
    response.raise_for_status()
    return response.json()

@handle_api_error
def make_post_request(url, data, auth, timeout=30):
    """Membuat permintaan POST ke API."""
    # Mengonversi semua nilai data menjadi string untuk konsistensi
    str_data = {k: str(v) for k, v in data.items()}
    response = requests.post(url, data=str_data, auth=auth, timeout=timeout)
    response.raise_for_status()
    return response.json()

# --- Fungsi API Nadia Store (Berdasarkan Postman Collection Terbaru) ---
def get_saldo(email_anda: str, password_anda: str, key_anda: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/saldo"
    params = {"nadiastore": key_anda}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def get_list_paket(email_anda: str, password_anda: str, key_anda: str, jenis_paket: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/list_paket"
    params = {"nadiastore": key_anda, "jenis": jenis_paket}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def get_otp(email_anda: str, password_anda: str, key_anda: str, no_hp: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/get_otp"
    data = {"nadiastore": key_anda, "no_hp": no_hp, "metode": "OTP"}
    auth = (email_anda, password_anda)
    return make_post_request(url, data, timeout=90, auth=auth) # Timeout lebih lama untuk OTP

def login_sms(email_anda: str, password_anda: str, key_anda: str, no_hp: str, auth_id: str, kode_otp: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/login_sms"
    data = {"nadiastore": key_anda, "no_hp": no_hp, "metode": "OTP", "auth_id": auth_id, "kode_otp": kode_otp}
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def beli_paket_non_otp(email_anda: str, password_anda: str, key_anda: str, package_id: str, no_hp: str, price_or_fee: int) -> dict:
    """Melakukan pembelian paket Non-OTP dari API Nadia Store."""
    url = "https://api.melinda-store.my.id/v2/beli/nonotp"
    data = {
        "nadiastore": key_anda,
        "package_id": package_id,
        "no_hp": no_hp,
        "uri": "package_purchase_non_otp",
        "price_or_fee": price_or_fee,
        "url_callback": URL_CALLBACK_ANDA # Menggunakan URL callback dari konfigurasi
    }
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def beli_paket_otp(email_anda: str, password_anda: str, key_anda: str, package_id: str, no_hp: str, access_token: str, price_or_fee: int, payment_method: str) -> dict:
    """Melakukan pembelian paket OTP dari API Nadia Store."""
    url = "https://api.melinda-store.my.id/v2/beli/otp"
    data = { 
        "nadiastore": key_anda,
        "package_id": package_id,
        "no_hp": no_hp,
        "access_token": access_token,
        "uri": "package_purchase_otp",
        "payment_method": payment_method,
        "price_or_fee": price_or_fee,
        "url_callback": URL_CALLBACK_ANDA # Menggunakan URL callback dari konfigurasi
    }
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def cek_status_transaksi(email_anda: str, password_anda: str, key_anda: str, trx_id: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/cekStatus"
    params = {"nadiastore": key_anda, "trx_id": trx_id}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def detail_paket(email_anda: str, password_anda: str, key_anda: str, access_token: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/detail_paket"
    params = {"nadiastore": key_anda, "access_token": access_token}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def unreg_paket(email_anda: str, password_anda: str, key_anda: str, data: dict) -> dict:
    url = "https://api.melinda-store.my.id/v2/unreg"
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def cek_stok_akrab(email_anda: str, password_anda: str, key_anda: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/cek_stok_akrab"
    params = {"nadiastore": key_anda}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def detail_pengelola(email_anda: str, password_anda: str, key_anda: str, parent_msisdn: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/akrab/detailPengelola"
    params = {"nadiastore": key_anda, "parent_msisdn": parent_msisdn}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def invite_member(email_anda: str, password_anda: str, key_anda: str, data: dict) -> dict:
    url = "https://api.melinda-store.my.id/v2/akrab/inviteMember"
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def kick_member(email_anda: str, password_anda: str, key_anda: str, data: dict) -> dict:
    url = "https://api.melinda-store.my.id/v2/akrab/kickAnggota"
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def set_kuota(email_anda: str, password_anda: str, key_anda: str, data: dict) -> dict:
    url = "https://api.melinda-store.my.id/v2/akrab/setKuota"
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def cek_sesi_login(email_anda: str, password_anda: str, key_anda: str, no_hp: str) -> dict:
    url = "https://api.melinda-store.my.id/v2/cek_sesi_login"
    params = {"nadiastore": key_anda, "no_hp": no_hp}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

# --- NEW API FUNCTIONS ---
def add_pengelola(email_anda: str, password_anda: str, key_anda: str, package_id: str, parent_msisdn: str, price_or_fee: int) -> dict:
    """Menambahkan nomor sebagai pengelola paket Akrab."""
    url = "https://api.melinda-store.my.id/v2/akrab/addPengelola"
    data = {
        "nadiastore": key_anda,
        "package_id": package_id,
        "parent_msisdn": parent_msisdn,
        "price_or_fee": price_or_fee
    }
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def get_list_pengelola(email_anda: str, password_anda: str, key_anda: str) -> dict:
    """Mendapatkan daftar pengelola Akrab yang terdaftar di akun Anda."""
    url = "https://api.melinda-store.my.id/v2/akrab/pengelola"
    params = {"nadiastore": key_anda}
    auth = (email_anda, password_anda)
    return make_get_request(url, params, auth)

def delete_pengelola(email_anda: str, password_anda: str, key_anda: str, id_parent: str) -> dict:
    """Menghapus pengelola Akrab."""
    url = "https://api.melinda-store.my.id/v2/akrab/deletePengelola"
    data = {
        "nadiastore": key_anda,
        "id_parent": id_parent
    }
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

def beli_extra_slot(email_anda: str, password_anda: str, key_anda: str, package_id: str, parent_msisdn: str, price_or_fee: int) -> dict:
    """Membeli slot tambahan untuk paket Akrab."""
    url = "https://api.melinda-store.my.id/v2/akrab/beliSlot"
    data = {
        "nadiastore": key_anda,
        "package_id": package_id,
        "parent_msisdn": parent_msisdn,
        "price_or_fee": price_or_fee
    }
    auth = (email_anda, password_anda)
    return make_post_request(url, data, auth)

# --- Fungsi Logika Pembelian & Manajemen ---
def login_otp_flow(email, password, api_key):
    """Menangani alur login OTP dan mengembalikan access_token."""
    global sesi_login
    access_token = None
    no_hp = None

    while True:
        no_hp_input = input(f"{Colors.WARNING}Masukkan nomor telepon tujuan (contoh: 081234567890) atau '0' untuk kembali: {Colors.ENDC}").strip()
        if no_hp_input.lower() == '0': return None, None
        if no_hp_input.isdigit() and len(no_hp_input) > 9:
            no_hp = format_phone_number(no_hp_input)
            break
        else: print(f"{Colors.FAIL}Nomor telepon tidak valid. Harap masukkan nomor yang benar.{Colors.ENDC}")
    
    if no_hp in sesi_login:
        print(f"\n{Colors.PRIMARY}{Colors.BOLD}Sesi login tersimpan ditemukan untuk nomor {no_hp}. Memvalidasi...{Colors.ENDC}")
        sesi_valid_response = cek_sesi_login(email, password, api_key, no_hp)
        if sesi_valid_response and sesi_valid_response.get('status'):
            print(f"{Colors.SUCCESS}Sesi masih valid.{Colors.ENDC}")
            access_token = sesi_login[no_hp]
        else:
            print(f"{Colors.WARNING}Sesi sudah kedaluwarsa. Anda perlu login ulang.{Colors.ENDC}")
            sesi_login.pop(no_hp, None)
            simpan_sesi(sesi_login)

    if not access_token:
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Meminta Kode OTP ---{Colors.ENDC}")
        otp_response = get_otp(email, password, api_key, no_hp)
        
        if not otp_response or not otp_response.get("status"):
            print(f"{Colors.FAIL}Gagal meminta OTP: {otp_response.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
            return None, None
        
        auth_id = otp_response.get("data", {}).get("auth_id")
        if not auth_id:
            print(f"{Colors.FAIL}Gagal mendapatkan ID otentikasi dari respons OTP.{Colors.ENDC}")
            return None, None
            
        print(f"{Colors.SUCCESS}Kode OTP telah dikirim ke nomor Anda.{Colors.ENDC}")
        kode_otp = input(f"{Colors.WARNING}Masukkan kode OTP yang Anda terima: {Colors.ENDC}").strip()
        
        login_response = login_sms(email, password, api_key, no_hp, auth_id, kode_otp)
        if not login_response or not login_response.get("status"):
            print(f"{Colors.FAIL}Login dengan OTP gagal: {login_response.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
            return None, None
            
        access_token = login_response.get("data", {}).get("access_token")
        if not access_token:
            print(f"{Colors.FAIL}Gagal mendapatkan access token setelah login.{Colors.ENDC}")
            return None, None
        
        sesi_login[no_hp] = access_token
        simpan_sesi(sesi_login)
        print("\n" + "-"*35)
        print(f"{Colors.SUCCESS}{Colors.BOLD}Verifikasi OTP berhasil!{Colors.ENDC}")
        print(f"{Colors.PRIMARY}Nomor Terverifikasi: {no_hp}{Colors.ENDC}")
        print(f"{Colors.INFO}Status: Sesi login baru telah disimpan, aman!.{Colors.ENDC}")
        print("-"*35)
    
    return no_hp, access_token

def proses_pembelian_paket(email, password, api_key, jenis_paket):
    """Menangani seluruh proses pemilihan dan pembelian paket."""
    no_hp, access_token = None, None

    if jenis_paket == "otp":
        no_hp, access_token = login_otp_flow(email, password, api_key)
        if not access_token:
            print(f"{Colors.FAIL}Proses login OTP gagal. Kembali ke menu utama.{Colors.ENDC}")
            return

    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Mengambil Daftar Paket {jenis_paket.upper()} ---{Colors.ENDC}")
    paket_data = get_list_paket(email, password, api_key, jenis_paket=jenis_paket)

    if not paket_data or not paket_data.get("status"):
        print(f"{Colors.FAIL}Gagal mengambil daftar paket: {paket_data.get('message', 'Tidak ada pesan error')}{Colors.ENDC}")
        return

    paket_list = paket_data.get("data", [])
    if not paket_list:
        print(f"{Colors.WARNING}Tidak ada paket yang tersedia saat ini.{Colors.ENDC}")
        return

    print(f"{Colors.ACCENT}{'-' * 90}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'No.':<5}{'Nama Paket':<50}{'Kode':<20}{'Harga':<15}{Colors.ENDC}")
    print(f"{Colors.ACCENT}{'-' * 90}{Colors.ENDC}")
    for i, paket in enumerate(paket_list):
        nama_paket = paket['package_name_show']
        if len(nama_paket) > 48:
            nama_paket = nama_paket[:45] + "..."
        print(f"{Colors.PRIMARY}{i + 1:<5}{nama_paket:<50}{paket['package_code']:<20}{paket['harga']:<15}{Colors.ENDC}")
    print(f"{Colors.ACCENT}{'-' * 90}{Colors.ENDC}")

    while True:
        try:
            pilihan = int(input(f"{Colors.WARNING}Pilih nomor paket (1-{len(paket_list)}), atau 0 untuk kembali: {Colors.ENDC}").strip())
            if 0 <= pilihan <= len(paket_list): break
            else: print(f"{Colors.FAIL}Pilihan tidak valid.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.FAIL}Masukkan nomor yang valid.{Colors.ENDC}")

    if pilihan == 0: return

    paket_terpilih = paket_list[pilihan - 1]
    package_id = paket_terpilih['package_id']
    harga_paket = paket_terpilih['harga_int']
    print(f"\nAnda memilih: {Colors.ACCENT}{Colors.BOLD}{paket_terpilih['package_name_show']}{Colors.ENDC}")
    print(f"Harga: {Colors.ACCENT}{Colors.BOLD}{paket_terpilih['harga']}{Colors.ENDC}")
    
    saldo_data = get_saldo(email, password, api_key)
    if not saldo_data or not saldo_data.get("status"):
        print(f"{Colors.FAIL}Gagal memeriksa saldo. Pembelian tidak dapat dilanjutkan.{Colors.ENDC}")
        return
    
    saldo_saat_ini = saldo_data.get('data', {}).get('saldo', 0)
    if saldo_saat_ini < harga_paket:
        print(f"{Colors.FAIL}Pembelian Gagal: Saldo Anda (Rp. {saldo_saat_ini:,}) tidak mencukupi untuk membeli paket seharga Rp. {harga_paket:,}.{Colors.ENDC}")
        return
    print(f"{Colors.SUCCESS}Saldo mencukupi (Rp. {saldo_saat_ini:,}).{Colors.ENDC}")

    payment_method = None
    if jenis_paket == "otp":
        available_methods = paket_terpilih.get("payment_method", [])
        if available_methods:
            print(f"{Colors.PRIMARY}Metode pembayaran yang tersedia:{Colors.ENDC}")
            for i, method in enumerate(available_methods):
                print(f"{Colors.INFO}{i + 1}. {method}{Colors.ENDC}")
            while True:
                try:
                    pilihan_metode = int(input(f"{Colors.WARNING}Pilih metode pembayaran (1-{len(available_methods)}): {Colors.ENDC}").strip())
                    if 1 <= pilihan_metode <= len(available_methods):
                        payment_method = available_methods[pilihan_metode - 1]
                        break
                    else: print(f"{Colors.FAIL}Pilihan tidak valid.{Colors.ENDC}")
                except ValueError:
                    print(f"{Colors.FAIL}Masukkan nomor yang valid.{Colors.ENDC}")
        else:
            # Jika tidak ada metode pembayaran, API mungkin akan menggunakan saldo akun.
            # Berikan nilai default yang masuk akal atau biarkan kosong jika API mengizinkan.
            payment_method = "SALDO" 
            print(f"{Colors.PRIMARY}Tidak ada metode pembayaran spesifik. Pembelian akan menggunakan saldo akun Anda.{Colors.ENDC}")

    if jenis_paket == "nonotp":
        while True:
            no_hp_input = input(f"{Colors.WARNING}Masukkan nomor telepon tujuan (contoh: 081234567890): {Colors.ENDC}").strip()
            if no_hp_input.isdigit() and len(no_hp_input) > 9:
                no_hp = format_phone_number(no_hp_input)
                break
            else: print(f"{Colors.FAIL}Nomor telepon tidak valid. Harap masukkan nomor yang benar.{Colors.ENDC}")

    konfirmasi = input(f"{Colors.WARNING}Apakah Anda yakin ingin membeli paket '{paket_terpilih['package_name_show']}' untuk nomor {no_hp}? (y/n): {Colors.ENDC}").strip().lower()
    if konfirmasi != 'y':
        print(f"{Colors.INFO}Pembelian dibatalkan.{Colors.ENDC}")
        return

    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Memproses Pembelian ---{Colors.ENDC}")
    if jenis_paket == "nonotp":
        hasil_pembelian = beli_paket_non_otp(email, password, api_key, package_id, no_hp, price_or_fee=harga_paket)
    else: # jenis_paket == "otp"
        hasil_pembelian = beli_paket_otp(email, password, api_key, package_id, no_hp, access_token, price_or_fee=harga_paket, payment_method=payment_method)

    if hasil_pembelian and hasil_pembelian.get("status"):
        print(f"{Colors.SUCCESS}Pembelian berhasil!{Colors.ENDC}")
        print(f"{Colors.INFO}Pesan dari server: {hasil_pembelian.get('message')}{Colors.ENDC}")
        data = hasil_pembelian.get('data', {})
        if data:
            print(f"{Colors.PRIMARY}Detail Transaksi:{Colors.ENDC}")
            for key, value in data.items():
                if isinstance(value, dict):
                    print(f"{Colors.INFO}- {key.replace('_', ' ').title()}:{Colors.ENDC}")
                    for sub_key, sub_value in value.items():
                        print(f"  {Colors.INFO}- {sub_key.replace('_', ' ').title()}: {sub_value}{Colors.ENDC}")
                else:
                    print(f"{Colors.INFO}- {key.replace('_', ' ').title()}: {value}{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}Pembelian Gagal.{Colors.ENDC}")
        if hasil_pembelian:
            pesan_error = hasil_pembelian.get('message')
            if pesan_error is None:
                pesan_error = f"Server memberikan respons gagal tanpa pesan spesifik. Respons penuh: {json.dumps(hasil_pembelian)}"
        else:
            pesan_error = 'Tidak ada respons dari server.'
        print(f"{Colors.FAIL}Pesan dari server: {pesan_error}{Colors.ENDC}")

def get_package_info_by_type(email, password, api_key, jenis_paket_type):
    """
    Fungsi pembantu untuk mendapatkan package_id dan harga_int dari jenis paket tertentu.
    Digunakan untuk 'pa' (add pengelola) dan 'bes' (beli extra slot).
    """
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Mengambil informasi paket untuk '{jenis_paket_type}' ---{Colors.ENDC}")
    paket_data = get_list_paket(email, password, api_key, jenis_paket=jenis_paket_type)

    if not paket_data or not paket_data.get("status"):
        print(f"{Colors.FAIL}Gagal mengambil daftar paket '{jenis_paket_type}': {paket_data.get('message', 'Tidak ada pesan error')}{Colors.ENDC}")
        return None, None

    paket_list = paket_data.get("data", [])
    if not paket_list:
        print(f"{Colors.WARNING}Tidak ada paket '{jenis_paket_type}' yang tersedia saat ini.{Colors.ENDC}")
        return None, None
    
    # Asumsi hanya ada satu jenis paket untuk 'pa' atau 'bes'
    if len(paket_list) > 1:
        print(f"{Colors.WARNING}Peringatan: Ditemukan lebih dari satu paket untuk '{jenis_paket_type}'. Menggunakan yang pertama.{Colors.ENDC}")
    
    paket_terpilih = paket_list[0]
    return paket_terpilih['package_id'], paket_terpilih['harga_int']

def manajemen_akrab_menu(email, password, api_key):
    """Menampilkan menu untuk manajemen Paket Akrab."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}--- Manajemen Paket Akrab ---{Colors.ENDC}")
    
    no_hp, access_token = login_otp_flow(email, password, api_key)
    if not access_token:
        print(f"{Colors.FAIL}Proses login OTP gagal. Kembali ke menu utama.{Colors.ENDC}")
        return

    while True:
        os.system('cls' if os.name == 'nt' else 'clear') # CLEAR SCREEN
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Opsi Manajemen Akrab ---{Colors.ENDC}")
        print(f"{Colors.PRIMARY}1. Detail Pengelola Akrab (termasuk anggota){Colors.ENDC}")
        print(f"{Colors.PRIMARY}2. Undang Anggota Baru{Colors.ENDC}")
        print(f"{Colors.PRIMARY}3. Atur Kuota Anggota (Kuber){Colors.ENDC}")
        print(f"{Colors.PRIMARY}4. Keluarkan Anggota{Colors.ENDC}")
        print(f"{Colors.PRIMARY}5. Tambah Pengelola Akrab Baru{Colors.ENDC}") # New
        print(f"{Colors.PRIMARY}6. Lihat Daftar Pengelola Akrab{Colors.ENDC}") # New
        print(f"{Colors.PRIMARY}7. Hapus Pengelola Akrab{Colors.ENDC}") # New
        print(f"{Colors.PRIMARY}8. Beli Slot Akrab Tambahan{Colors.ENDC}") # New
        print(f"{Colors.PRIMARY}9. Kembali ke Menu Utama{Colors.ENDC}")
        pilihan = input(f"{Colors.WARNING}Pilih opsi: {Colors.ENDC}").strip()

        if pilihan == '1':
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Detail Pengelola Akrab ---{Colors.ENDC}")
            detail_data = detail_pengelola(email, password, api_key, no_hp)
            if not detail_data or not detail_data.get("status"):
                print(f"{Colors.FAIL}Gagal mendapatkan detail pengelola: {detail_data.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            parent_data = detail_data.get('data', {}).get('parent_data', {})
            if parent_data:
                print(f"{Colors.INFO}Nomor Pengelola: {parent_data.get('parent_msisdn')}{Colors.ENDC}")
                print(f"{Colors.INFO}Kuota Dialokasikan: {parent_data.get('quota_allocated')}{Colors.ENDC}")
                print(f"{Colors.INFO}Kuota Terpakai: {parent_data.get('quota_used')}{Colors.ENDC}")
                print(f"{Colors.INFO}Aktif Sampai: {parent_data.get('active_until')}{Colors.ENDC}")
            else:
                print(f"{Colors.WARNING}Data pengelola tidak ditemukan untuk nomor {no_hp}.{Colors.ENDC}")

            members = detail_data.get('data', {}).get('members_slot_data_from_our_database', [])
            if not members:
                print(f"{Colors.WARNING}Tidak ada anggota dalam paket ini.{Colors.ENDC}")
            else:
                print(f"\n{Colors.HEADER}{Colors.BOLD}--- Daftar Anggota ---{Colors.ENDC}")
                print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
                print(f"{Colors.BOLD}{'No.':<5}{'MSISDN Anggota':<20}{'Alias':<20}{'Kuota Dialokasikan':<25}{'Status Slot':<10}{Colors.ENDC}")
                print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
                for i, member in enumerate(members):
                    member_no = member.get('member_msisdn') if member.get('member_msisdn') else "[SLOT KOSONG]"
                    member_alias = member.get('member_alias') if member.get('member_alias') else "-"
                    quota_allocated = member.get('usage', {}).get('quota_allocated_in_human_readable_text', 'N/A')
                    slot_status = "Dihapus" if member.get('is_slot_has_been_deleted') else ("Kosong" if not member.get('member_msisdn') else "Aktif")
                    print(f"{Colors.PRIMARY}{i + 1:<5}{member_no:<20}{member_alias:<20}{quota_allocated:<25}{slot_status:<10}{Colors.ENDC}")
                print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '2': # Undang Anggota Baru
            slot_kosong_ditemukan = False
            detail_data = detail_pengelola(email, password, api_key, no_hp)
            if detail_data and detail_data.get("status"):
                members = detail_data.get('data', {}).get('members_slot_data_from_our_database', [])
                for member in members:
                    if not member.get('member_msisdn') and not member.get('is_slot_has_been_deleted'):
                        slot_kosong_ditemukan = True
                        print(f"\n{Colors.PRIMARY}Slot kosong ditemukan (Slot ID: {member['slot_id']}).{Colors.ENDC}")
                        
                        package_id_invite, price_invite = get_package_info_by_type(email, password, api_key, 'invite')
                        if not package_id_invite:
                            print(f"{Colors.FAIL}Gagal mendapatkan Package ID untuk invite anggota. Pembelian tidak dapat dilanjutkan.{Colors.ENDC}")
                            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                            continue

                        new_member_no_input = input(f"{Colors.WARNING}Masukkan nomor anggota baru (contoh: 081234567890) atau 'batal' untuk kembali: {Colors.ENDC}").strip()
                        if new_member_no_input.lower() == 'batal': continue
                        if not (new_member_no_input.isdigit() and len(new_member_no_input) > 9):
                            print(f"{Colors.FAIL}Nomor telepon tidak valid. Harap masukkan nomor yang benar.{Colors.ENDC}")
                            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                            continue
                        new_member_no = format_phone_number(new_member_no_input)

                        pengelola_alias = input(f"{Colors.WARNING}Masukkan alias pengelola (opsional, default: Pengelola): {Colors.ENDC}").strip() or "Pengelola"
                        member_alias = input(f"{Colors.WARNING}Masukkan alias anggota (opsional, default: Anggota): {Colors.ENDC}").strip() or "Anggota"

                        konfirmasi = input(f"{Colors.WARNING}Yakin ingin mengundang {new_member_no} ke slot {member['slot_id']}? (y/n): {Colors.ENDC}").strip().lower()
                        if konfirmasi != 'y':
                            print(f"{Colors.INFO}Undangan dibatalkan.{Colors.ENDC}")
                            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                            continue

                        data_invite = {
                            "nadiastore": api_key,
                            "package_id": package_id_invite,
                            "parent_msisdn": no_hp,
                            "slot_id": member['slot_id'],
                            "family_member_id_pre_invite": member['family_member_id_pre_invite'],
                            "member_msisdn": new_member_no,
                            "pengelola_alias": pengelola_alias,
                            "member_alias": member_alias,
                            "invite_bypass_mode_enabled": "N",
                            "price_or_fee": price_invite
                        }
                        invite_res = invite_member(email, password, api_key, data_invite)
                        if invite_res and invite_res.get('status'):
                            print(f"{Colors.SUCCESS}Berhasil mengirim undangan!{Colors.ENDC}")
                        else:
                            print(f"{Colors.FAIL}Gagal mengundang: {invite_res.get('message', 'Error')}{Colors.ENDC}")
                        input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                        break # Keluar dari loop setelah menemukan dan mencoba mengundang ke satu slot kosong
                
                if not slot_kosong_ditemukan:
                    print(f"{Colors.WARNING}Tidak ada slot kosong yang tersedia untuk diundang.{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal mendapatkan detail pengelola untuk mencari slot kosong: {detail_data.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '3' or pilihan == '4':
            detail_data = detail_pengelola(email, password, api_key, no_hp)
            if not detail_data or not detail_data.get("status"):
                print(f"{Colors.FAIL}Gagal mendapatkan detail pengelola: {detail_data.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue
            members = [m for m in detail_data.get('data', {}).get('members_slot_data_from_our_database', []) if m.get('member_msisdn')]
            if not members:
                print(f"{Colors.WARNING}Tidak ada anggota aktif untuk dipilih.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Pilih Anggota ---{Colors.ENDC}")
            for i, member in enumerate(members):
                print(f"{Colors.PRIMARY}{i + 1}. {member['member_msisdn']} (Kuota: {member['usage']['quota_allocated_in_human_readable_text']}){Colors.ENDC}")
            
            try:
                pilihan_member_idx = int(input(f"{Colors.WARNING}Pilih nomor anggota (1-{len(members)}), atau 0 untuk kembali: {Colors.ENDC}").strip()) - 1
                if not (0 <= pilihan_member_idx < len(members)):
                    if pilihan_member_idx == -1: # User entered 0
                        print(f"{Colors.INFO}Operasi dibatalkan.{Colors.ENDC}")
                    else:
                        print(f"{Colors.FAIL}Pilihan tidak valid.{Colors.ENDC}")
                    input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                    continue
                member_terpilih = members[pilihan_member_idx]

                if pilihan == '3': # Atur Kuota
                    kuota_gb_input = input(f"{Colors.WARNING}Masukkan jumlah kuota baru dalam GB (contoh: 5.5): {Colors.ENDC}").strip()
                    try:
                        kuota_gb = float(kuota_gb_input)
                        if kuota_gb < 0:
                            print(f"{Colors.FAIL}Kuota tidak bisa negatif.{Colors.ENDC}")
                            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                            continue
                    except ValueError:
                        print(f"{Colors.FAIL}Input kuota tidak valid. Harap masukkan angka.{Colors.ENDC}")
                        input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                        continue

                    konfirmasi = input(f"{Colors.WARNING}Yakin ingin mengatur kuota {member_terpilih['member_msisdn']} menjadi {kuota_gb} GB? (y/n): {Colors.ENDC}").lower()
                    if konfirmasi == 'y':
                        data_kuota = {
                            "nadiastore": api_key,
                            "parent_msisdn": no_hp,
                            "family_member_id_invited": member_terpilih['family_member_id_invited'],
                            "set_kuota_ke_in_gb": kuota_gb
                        }
                        set_res = set_kuota(email, password, api_key, data_kuota)
                        if set_res and set_res.get('status'):
                            print(f"{Colors.SUCCESS}Berhasil mengatur kuota!{Colors.ENDC}")
                        else:
                            print(f"{Colors.FAIL}Gagal mengatur kuota: {set_res.get('message', 'Error')}{Colors.ENDC}")
                    else:
                        print(f"{Colors.INFO}Pengaturan kuota dibatalkan.{Colors.ENDC}")
                    input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

                elif pilihan == '4': # Keluarkan Anggota
                    konfirmasi = input(f"{Colors.WARNING}Yakin ingin mengeluarkan {member_terpilih['member_msisdn']}? (y/n): {Colors.ENDC}").lower()
                    if konfirmasi == 'y':
                        data_kick = {
                            "nadiastore": api_key,
                            "parent_msisdn": no_hp,
                            "family_member_id_invited": member_terpilih['family_member_id_invited']
                        }
                        kick_res = kick_member(email, password, api_key, data_kick)
                        if kick_res and kick_res.get('status'):
                            print(f"{Colors.SUCCESS}Berhasil mengeluarkan anggota!{Colors.ENDC}")
                        else:
                            print(f"{Colors.FAIL}Gagal mengeluarkan anggota: {kick_res.get('message', 'Error')}{Colors.ENDC}")
                    else:
                        print(f"{Colors.INFO}Pengeluaran anggota dibatalkan.{Colors.ENDC}")
                    input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.FAIL}Masukkan nomor yang valid.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '5': # Tambah Pengelola Akrab Baru
            package_id_pa, price_pa = get_package_info_by_type(email, password, api_key, 'pa')
            if not package_id_pa:
                print(f"{Colors.FAIL}Gagal mendapatkan Package ID untuk tambah pengelola. Operasi dibatalkan.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            new_parent_msisdn_input = input(f"{Colors.WARNING}Masukkan nomor telepon pengelola baru (contoh: 081234567890) atau 'batal' untuk kembali: {Colors.ENDC}").strip()
            if new_parent_msisdn_input.lower() == 'batal': 
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue
            if not (new_parent_msisdn_input.isdigit() and len(new_parent_msisdn_input) > 9):
                print(f"{Colors.FAIL}Nomor telepon tidak valid. Harap masukkan nomor yang benar.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue
            new_parent_msisdn = format_phone_number(new_parent_msisdn_input)

            konfirmasi = input(f"{Colors.WARNING}Yakin ingin menambahkan {new_parent_msisdn} sebagai pengelola baru? (y/n): {Colors.ENDC}").strip().lower()
            if konfirmasi != 'y':
                print(f"{Colors.INFO}Penambahan pengelola dibatalkan.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            add_res = add_pengelola(email, password, api_key, package_id_pa, new_parent_msisdn, price_pa)
            if add_res and add_res.get('status'):
                print(f"{Colors.SUCCESS}Pengelola berhasil ditambahkan!{Colors.ENDC}")
                data_res = add_res.get('data', {})
                if data_res:
                    print(f"{Colors.PRIMARY}Detail Pengelola Baru:{Colors.ENDC}")
                    print(f"{Colors.INFO}- ID Parent: {data_res.get('id_parent')}{Colors.ENDC}")
                    print(f"{Colors.INFO}- Nomor Pengelola: {data_res.get('parent_msisdn')}{Colors.ENDC}")
                    print(f"{Colors.INFO}- Aktif Dari: {data_res.get('start_date')}{Colors.ENDC}")
                    print(f"{Colors.INFO}- Aktif Sampai: {data_res.get('end_date')}{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal menambahkan pengelola: {add_res.get('message', 'Error')}{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '6': # Lihat Daftar Pengelola Akrab
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Daftar Pengelola Akrab ---{Colors.ENDC}")
            list_pengelola_data = get_list_pengelola(email, password, api_key)
            if list_pengelola_data and list_pengelola_data.get('status'):
                pengelola_list = list_pengelola_data.get('data', [])
                if pengelola_list:
                    print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
                    print(f"{Colors.BOLD}{'No.':<5}{'MSISDN Pengelola':<20}{'ID Parent':<40}{'Aktif Sampai':<15}{Colors.ENDC}")
                    print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
                    for i, pengelola in enumerate(pengelola_list):
                        print(f"{Colors.PRIMARY}{i + 1:<5}{pengelola.get('parent_msisdn', 'N/A'):<20}{pengelola.get('id_parent', 'N/A'):<40}{pengelola.get('end_date', 'N/A'):<15}{Colors.ENDC}")
                    print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
                else:
                    print(f"{Colors.WARNING}Tidak ada pengelola akrab yang terdaftar.{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal mengambil daftar pengelola: {list_pengelola_data.get('message', 'Error')}{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '7': # Hapus Pengelola Akrab
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Hapus Pengelola Akrab ---{Colors.ENDC}")
            list_pengelola_data = get_list_pengelola(email, password, api_key)
            if not list_pengelola_data or not list_pengelola_data.get('status'):
                print(f"{Colors.FAIL}Gagal mengambil daftar pengelola untuk dihapus: {list_pengelola_data.get('message', 'Error')}{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue
            
            pengelola_list = list_pengelola_data.get('data', [])
            if not pengelola_list:
                print(f"{Colors.WARNING}Tidak ada pengelola untuk dihapus.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
            print(f"{Colors.BOLD}{'No.':<5}{'MSISDN Pengelola':<20}{'ID Parent':<40}{'Aktif Sampai':<15}{Colors.ENDC}")
            print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")
            for i, pengelola in enumerate(pengelola_list):
                print(f"{Colors.PRIMARY}{i + 1:<5}{pengelola.get('parent_msisdn', 'N/A'):<20}{pengelola.get('id_parent', 'N/A'):<40}{pengelola.get('end_date', 'N/A'):<15}{Colors.ENDC}")
            print(f"{Colors.ACCENT}{'-' * 80}{Colors.ENDC}")

            try:
                pilihan_pengelola_idx = int(input(f"{Colors.WARNING}Pilih nomor pengelola yang akan dihapus (1-{len(pengelola_list)}), atau 0 untuk kembali: {Colors.ENDC}").strip()) - 1
                if not (0 <= pilihan_pengelola_idx < len(pengelola_list)):
                    if pilihan_pengelola_idx == -1:
                        print(f"{Colors.INFO}Penghapusan pengelola dibatalkan.{Colors.ENDC}")
                    else:
                        print(f"{Colors.FAIL}Pilihan tidak valid.{Colors.ENDC}")
                    input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                    continue
                pengelola_terpilih = pengelola_list[pilihan_pengelola_idx]

                konfirmasi = input(f"{Colors.WARNING}Yakin ingin menghapus pengelola {pengelola_terpilih.get('parent_msisdn')} (ID: {pengelola_terpilih.get('id_parent')})? (y/n): {Colors.ENDC}").lower()
                if konfirmasi == 'y':
                    delete_res = delete_pengelola(email, password, api_key, pengelola_terpilih.get('id_parent'))
                    if delete_res and delete_res.get('status'):
                        print(f"{Colors.SUCCESS}Pengelola berhasil dihapus!{Colors.ENDC}")
                    else:
                        print(f"{Colors.FAIL}Gagal menghapus pengelola: {delete_res.get('message', 'Error')}{Colors.ENDC}")
                else:
                    print(f"{Colors.INFO}Penghapusan pengelola dibatalkan.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.FAIL}Masukkan nomor yang valid.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '8': # Beli Slot Akrab Tambahan
            package_id_bes, price_bes = get_package_info_by_type(email, password, api_key, 'bes')
            if not package_id_bes:
                print(f"{Colors.FAIL}Gagal mendapatkan Package ID untuk beli extra slot. Operasi dibatalkan.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue
            
            # Asumsi parent_msisdn adalah nomor yang sedang login
            current_parent_msisdn = no_hp 

            konfirmasi = input(f"{Colors.WARNING}Yakin ingin membeli slot tambahan untuk pengelola {current_parent_msisdn} seharga Rp. {price_bes:,}? (y/n): {Colors.ENDC}").strip().lower()
            if konfirmasi != 'y':
                print(f"{Colors.INFO}Pembelian slot dibatalkan.{Colors.ENDC}")
                input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")
                continue

            beli_slot_res = beli_extra_slot(email, password, api_key, package_id_bes, current_parent_msisdn, price_bes)
            if beli_slot_res and beli_slot_res.get('status'):
                print(f"{Colors.SUCCESS}Pembelian slot tambahan berhasil!{Colors.ENDC}")
                print(f"{Colors.INFO}Pesan dari server: {beli_slot_res.get('message')}{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal membeli slot tambahan: {beli_slot_res.get('message', 'Error')}{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

        elif pilihan == '9':
            break
        else:
            print(f"{Colors.FAIL}Pilihan tidak valid. Silakan coba lagi.{Colors.ENDC}")
            input(f"\n{Colors.ACCENT}Tekan Enter untuk melanjutkan...{Colors.ENDC}")

def show_donate_menu():
    """Menampilkan menu donasi dengan redirect tanpa konfirmasi."""
    DONATE_LINK = "https://saweria.co/VSTRA" # Link donasi Anda

    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.PRIMARY}Silakan kunjungi tautan berikut untuk berdonasi:{Colors.ENDC}")
    print(f"{Colors.ACCENT}{Colors.BOLD}          {DONATE_LINK}{Colors.ENDC}") 
    time.sleep(3)

    # Validasi tautan donasi (opsional, bisa disesuaikan)
    if not (DONATE_LINK.startswith("http://") or DONATE_LINK.startswith("https://")):
        print(f"{Colors.FAIL}Error: Tautan donasi tidak valid. Harap periksa DONATE_LINK di kode.{Colors.ENDC}")
        input(f"\n{Colors.ACCENT}Tekan Enter untuk kembali...{Colors.ENDC}")
        return # Keluar dari fungsi jika tautan tidak valid

    webbrowser.open(DONATE_LINK)
    time.sleep(2) # Beri sedikit waktu untuk browser terbuka
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Pesan informasi setelah redirect, tanpa konfirmasi
    print(f"{Colors.SUCCESS}Terima kasih telah mengunjungi tautan donasi! Kembali ke menu utama...{Colors.ENDC}")
    time.sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')


def type_effect(text, color=Colors.PRIMARY, delay=0.01):
    """Menampilkan teks dengan efek ketikan."""
    for char in text:
        sys.stdout.write(f"{color}{char}{Colors.ENDC}")
        sys.stdout.flush()
        time.sleep(delay)
    print() # Newline after typing

def fade_in_text(text, color=Colors.PRIMARY, steps=10, delay=0.05):
    """Menampilkan teks dengan efek fade-in (simulasi dengan intensitas warna)."""
    for i in range(1, steps + 1):
        # ANSI 256-color codes for grayscale (approximate fade)
        # Adjusting brightness from dark to light
        fade_color = f"\033[38;5;{232 + int((255 - 232) * i / steps)}m"
        sys.stdout.write(f"\r{fade_color}{text}{Colors.ENDC}")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(f"\r{color}{text}{Colors.ENDC}\n") # Final color and newline

def animate_ascii_logo(logo_lines, color=Colors.ACCENT): # Menghapus parameter delay_per_line
    
    print(f"{color}{logo_lines}{Colors.ENDC}")
    time.sleep(0.1) # Menambahkan jeda singkat setelah seluruh logo selesai diketik

# --- Fungsi Menu Utama ---
def main_menu():
    """Menampilkan menu utama dan menangani pilihan pengguna."""
    global sesi_login
    sesi_login = muat_sesi()
    kredensial = muat_kredensial()
    email, password, api_key = None, None, None

    os.system('cls' if os.name == 'nt' else 'clear') # Membersihkan layar di awal
    
    # --- GitHub Redirect START ---
    GITHUB_LINK = "https://github.com/VIDD7"
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear') # Membersihkan layar setiap iterasi
        print(f"\n{Colors.PRIMARY}{Colors.BOLD}Untuk melanjutkan, mohon kunjungi dan ikuti akun GitHub saya:{Colors.ENDC}")
        time.sleep(2)
        
        # Validasi tautan GitHub
        if not GITHUB_LINK.startswith("https://github.com/"):
            print(f"{Colors.FAIL}Error: Tautan GitHub tidak valid. Harap periksa GITHUB_LINK di kode.{Colors.ENDC}")
            sys.exit(1) # Keluar dari program jika tautan tidak valid

        webbrowser.open(GITHUB_LINK)
        time.sleep(2) # Beri sedikit waktu untuk browser terbuka
        os.system('cls' if os.name == 'nt' else 'clear')

        konfirmasi_follow = input(f"{Colors.WARNING}Sudahkah Anda mengikuti akun GitHub saya? (y/n): {Colors.ENDC}").strip().lower()
        if konfirmasi_follow == 'y':
            print(f"{Colors.SUCCESS}Terima kasih telah mengikuti! Melanjutkan program...{Colors.ENDC}")
            time.sleep(1)
            os.system('cls' if os.name == 'nt' else 'clear')
            break
        elif konfirmasi_follow == 'n':
            print(f"{Colors.INFO}Mohon ikuti akun GitHub terlebih dahulu untuk melanjutkan.{Colors.ENDC}")
            time.sleep(2)
            # Loop akan berlanjut, membuka kembali tautan
        else:
            print(f"{Colors.FAIL}Input tidak valid. Harap jawab 'y' atau 'n'.{Colors.ENDC}")
            time.sleep(1)
    # --- GitHub Redirect END ---

    print("\n" + Colors.ACCENT + "="*60 + Colors.ENDC) 
    type_effect("                Selamat Datang di VITOOL!", Colors.HEADER, 0.03)
    time.sleep(0.3)
    type_effect("  Platform Manajemen Akrab & Pembelian Paket Data XL/AXIS", Colors.INFO, 0.03)
    time.sleep(0.3)
    print(Colors.ACCENT + "="*60 + Colors.ENDC + "\n") 
    time.sleep(0.3)

    if kredensial:
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Kredensial Ditemukan ---{Colors.ENDC}")
        print(f"{Colors.INFO}Email: {kredensial['email']}{Colors.ENDC}")
        gunakan_kredensial = input(f"{Colors.WARNING}Gunakan kredensial yang tersimpan? (y/n): {Colors.ENDC}").strip().lower()
        if gunakan_kredensial == 'y':
            email = kredensial['email']
            password = kredensial['password']
            api_key = kredensial['api_key']
            print(f"{Colors.SUCCESS}Menggunakan kredensial yang tersimpan.{Colors.ENDC}")
        else:
            # Hapus file kredensial jika tidak ingin menggunakannya 
            if os.path.exists(FILE_KREDENSIAL):
                os.remove(FILE_KREDENSIAL)
                print(f"{Colors.INFO}Kredensial lama telah dihapus.{Colors.ENDC}")

    if not all([email, password, api_key]):
        print(f"\n{Colors.HEADER}{Colors.BOLD}--- Masukkan akun yang sudah terdaftar ! ---{Colors.ENDC}")
        
        while True:
            email = input(f"{Colors.WARNING}Masukkan Email Anda: {Colors.ENDC}").strip()
            if not email:
                print(f"{Colors.FAIL}Email tidak boleh kosong. Silakan masukkan email Anda.{Colors.ENDC}")
            elif not validate_email(email):
                print(f"{Colors.FAIL}Format email tidak valid. Silakan masukkan email yang benar.{Colors.ENDC}")
            else:
                break

        while True:
            password = input(f"{Colors.WARNING}Masukkan Kata Sandi Anda: {Colors.ENDC}").strip()
            if not password:
                print(f"{Colors.FAIL}Kata sandi tidak boleh kosong. Silakan masukkan kata sandi Anda.{Colors.ENDC}")
            else:
                break

        while True:
            api_key = input(f"{Colors.WARNING}Masukkan API KEY Anda (nadiastore key): {Colors.ENDC}").strip()
            if not api_key:
                print(f"{Colors.FAIL}Kunci API tidak boleh kosong. Silakan masukkan kunci API Anda.{Colors.ENDC}")
            else:
                break
        
        simpan = input(f"{Colors.WARNING}Simpan kredensial ini untuk sesi berikutnya? (y/n): {Colors.ENDC}").strip().lower()
        if simpan == 'y':
            simpan_kredensial(email, password, api_key)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear') # CLEAR SCREEN
        print("\n" + Colors.HEADER + "="*47 + Colors.ENDC) 
        vitool_logo_ascii = r"""
  __      _______ _______ ____   ____  _      
  \ \    / /_  _|\__   __/ __ \ / __ \| |     
   \ \  / /  | |    | | | |  | | |  | | |     
    \ \/ /   | |    | | | |  | | |  | | |     
     \  /  __| |_   | | | |__| | |__| | |____ 
      \/  |_____|   |_|  \____/ \____/|______|
                                              
                    by vstra
"""
        animate_ascii_logo(vitool_logo_ascii, Colors.ACCENT) 

        print(f"{Colors.PRIMARY}{Colors.BOLD}Logged in: {email}{Colors.ENDC}")
        print(f"{Colors.INFO}Github: {GITHUB_LINK}{Colors.ENDC}") # Menggunakan GITHUB_LINK yang sudah didefinisikan
        print(f"{Colors.INFO}Website: https://vstra.my.id{Colors.ENDC}")
        print(Colors.HEADER + "="*47 + Colors.ENDC) 
        
        # Opsi menu dengan animasi ketikan yang lebih cepat
        menu_options = [
            "1. Cek Saldo",
            "2. Beli Paket Non-OTP",
            "3. Beli Paket OTP",
            "4. Cek Status Transaksi",
            "5. Manajemen Akrab",
            "6. Fitur Keren Lainnya",
            "7. Donate ke Admin Baik Hati Ini",
            "8. Keluar"
        ]
        for option in menu_options:
            type_effect(option, Colors.PRIMARY, delay=0.01) # Animasi ketikan lebih cepat
            time.sleep(0.05) # Jeda singkat antar baris menu
        
        print(Colors.HEADER + "="*47 + Colors.ENDC) 

        choice = input(f"{Colors.WARNING}Pilih opsi (1-8): {Colors.ENDC}").strip()

        # Menambahkan jeda visual setelah pilihan
        print(f"{Colors.INFO}Memproses pilihan Anda...{Colors.ENDC}")
        time.sleep(0.5) 

        if choice == '1':
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Memeriksa Saldo Anda ---{Colors.ENDC}")
            saldo_data = get_saldo(email, password, api_key)
            if saldo_data and saldo_data.get("status"):
                saldo = saldo_data.get('data', {}).get('saldo', 'Tidak tersedia')
                print(f"{Colors.SUCCESS}Saldo Anda: Rp. {saldo:,}{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal mengambil saldo: {saldo_data.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
        elif choice == '2':
            proses_pembelian_paket(email, password, api_key, "nonotp")
        elif choice == '3':
            proses_pembelian_paket(email, password, api_key, "otp")
        elif choice == '4':
            print(f"\n{Colors.HEADER}{Colors.BOLD}--- Cek Status Transaksi ---{Colors.ENDC}")
            trx_id = input(f"{Colors.WARNING}Masukkan ID Transaksi (trx_id): {Colors.ENDC}").strip()
            if not trx_id:
                print(f"{Colors.FAIL}ID Transaksi tidak boleh kosong.{Colors.ENDC}")
                continue
            status_data = cek_status_transaksi(email, password, api_key, trx_id)
            if status_data and status_data.get("status"):
                print(f"{Colors.SUCCESS}Berhasil mendapatkan status transaksi:{Colors.ENDC}")
                data = status_data.get('data', {})
                for key, value in data.items():
                    print(f"{Colors.INFO}- {key.replace('_', ' ').title()}: {value}{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}Gagal memeriksa status: {status_data.get('message', 'Error tidak diketahui')}{Colors.ENDC}")
        elif choice == '5':
            manajemen_akrab_menu(email, password, api_key)
        elif choice == '6':
            fitur_lainnya_menu(email, password, api_key)
        elif choice == '7': # New Donate Option
            show_donate_menu()
        elif choice == '8': # Changed from 7 to 8
            print(f"{Colors.SUCCESS}Terima kasih telah menggunakan VITOOL. Sampai jumpa!{Colors.ENDC}")
            break
        else:
            print(f"{Colors.FAIL}Pilihan tidak valid. Silakan coba lagi.{Colors.ENDC}")
        
        input(f"\n{Colors.ACCENT}Tekan Enter untuk kembali ke Menu Utama...{Colors.ENDC}") # Jeda agar user bisa membaca output

if __name__ == "__main__":
    main_menu()
