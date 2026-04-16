# 🔐 Secure File Sharing using Blockchain

A **production-ready**, end-to-end secure file sharing system powered by:
- **AES-256 encryption** (EAX mode — authenticated encryption)
- **SHA-256 integrity hashing** stored on an **Ethereum blockchain**
- **Flask REST API** backend with **JWT-style sessions**
- **SQLite database** for users, file metadata, and access control
- **Forgot Password** via OTP (no paid services required)
- Clean, dark-themed **HTML/CSS/JS frontend**

---

## 📁 Project Structure

```
SecureFileSharePro/
├── backend/
│   ├── app.py                        ← Flask entry point
│   ├── requirements.txt              ← Python dependencies
│   ├── deploy_contract.py            ← One-time contract deployment script
│   ├── routes/
│   │   ├── auth_routes.py            ← Register / Login / Logout / OTP
│   │   └── file_routes.py            ← Upload / Download / Verify / Share
│   ├── crypto/
│   │   └── encryption.py             ← AES-256 encrypt / decrypt
│   ├── blockchain/
│   │   └── web3_client.py            ← Web3.py contract interaction
│   ├── database/
│   │   └── db.py                     ← SQLite schema & connection
│   └── contracts/
│       ├── FileStorage_abi.json      ← Contract ABI (auto-generated)
│       ├── FileStorage_bytecode.txt  ← Contract bytecode (auto-generated)
│       └── deployed_address.txt      ← Deployed contract address (auto-generated)
├── contracts/
│   └── FileStorage.sol               ← Solidity smart contract
├── frontend/
│   ├── index.html                    ← Dashboard (upload/verify/download/share)
│   ├── login.html                    ← Login + Forgot Password
│   ├── register.html                 ← Registration
│   ├── script.js                     ← Frontend API integration
│   └── style.css                     ← Dark theme stylesheet
├── storage/                          ← Encrypted files stored here
└── database/                         ← SQLite DB stored here
```

---

## ⚙️ Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.9+ | https://python.org |
| Node.js | 16+ | https://nodejs.org |
| Ganache | latest | `npm install -g ganache` |

---

## 🚀 Setup & Run (Step by Step)

### Step 1 — Clone / Extract the project
```bash
cd SecureFileSharePro
```

### Step 2 — Start Ganache (local Ethereum blockchain)
Open a **new terminal** and run:
```bash
ganache --port 7545
```
Leave this terminal running. You should see 10 test accounts with 100 ETH each.

### Step 3 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 4 — Deploy the Smart Contract
```bash
cd backend
python deploy_contract.py
```
This will:
- Compile `contracts/FileStorage.sol` using solcx
- Deploy it to your local Ganache
- Save the ABI, bytecode, and deployed address into `backend/contracts/`

You only need to run this **once** per Ganache session.
> ⚠️ If you restart Ganache, run this script again (it clears the chain).

### Step 5 — Start the Flask backend
```bash
cd backend
python app.py
```
The API will be available at: `http://127.0.0.1:5000`

### Step 6 — Open the Frontend
Open `frontend/login.html` in your browser.

> **Tip:** Use VS Code Live Server or Python's HTTP server for best results:
> ```bash
> cd frontend
> python -m http.server 8080
> ```
> Then visit: `http://localhost:8080/login.html`

---

## 🔄 Full User Flow

```
Register → Login → Upload File
  ↓
  File is AES-256 encrypted
  SHA-256 hash stored on Ethereum blockchain
  Encrypted file saved to /storage/
  Metadata saved to SQLite DB
  ↓
View File List → Verify Integrity (checks blockchain)
  ↓
Download & Decrypt → Original file restored
  ↓
Share File with another user → They can download too
  ↓
Revoke access anytime
```

---

## 🔑 API Reference

### Auth Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login (returns session cookie) |
| POST | `/auth/logout` | Logout |
| GET  | `/auth/me` | Get current logged-in user |
| POST | `/auth/forgot-password` | Generate OTP for password reset |
| POST | `/auth/verify-otp` | Verify OTP and set new password |

### File Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/files/upload` | Upload, encrypt, and store hash on blockchain |
| GET  | `/files/list` | List owned + shared files |
| GET  | `/files/download/<id>` | Download and decrypt a file |
| GET  | `/files/verify/<id>` | Verify file integrity against blockchain |
| POST | `/files/share` | Share a file with another user |
| DELETE | `/files/revoke` | Revoke a user's access |

---

## 🗄️ Database Schema

```sql
users (id, username, email, password[bcrypt], created_at)
otp_store (id, username, otp, expires_at)
files (id, owner_username, original_name, stored_name,
       file_path, blockchain_hash, aes_key_hex, uploaded_at)
file_permissions (id, file_id, granted_to, granted_by, granted_at)
```

---

## 🔒 Security Features

| Feature | Implementation |
|---------|---------------|
| Password hashing | bcrypt with random salt |
| File encryption | AES-256-EAX (authenticated) |
| Key storage | Per-file key stored in DB, linked to file record |
| Integrity check | SHA-256 hash verified against blockchain |
| Session auth | Flask server-side sessions |
| Access control | Owner + explicitly granted users only |
| Input validation | All endpoints validate required fields |
| OTP expiry | 10-minute TTL on all OTPs |

---

## 🐛 Troubleshooting

**"Cannot connect to Ganache"**
→ Make sure Ganache is running: `ganache --port 7545`

**"Module not found"**
→ Run: `pip install -r requirements.txt` inside the `backend/` folder

**CORS errors in browser**
→ Make sure Flask is running on port 5000 and you are serving the frontend via a server (not `file://`)

**"OTP expired"**
→ OTPs expire after 10 minutes. Click "Forgot Password" again to get a new one.

---

## 🎓 Built For

**Secure File Sharing using Blockchain Technology**  
Demonstrates: AES-256, SHA-256, Ethereum, Web3.py, Flask, SQLite, bcrypt, OTP-based auth, access control.
