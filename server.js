require("dotenv").config();
const express = require("express");
const session = require("express-session");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const bcrypt = require("bcryptjs");
const Database = require("better-sqlite3");
const path = require("path");
const fs = require("fs");

const app = express();
const PORT = Number(process.env.PORT || 3000);
const dataDir = path.join(__dirname, "data");
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir);
const db = new Database(path.join(dataDir, "bike-resq.sqlite"));
db.pragma("journal_mode = WAL");
db.exec(`
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL,
 email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('customer','partner','admin')),
 service TEXT, area TEXT, phonepe_note TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL,
 service TEXT NOT NULL, details TEXT DEFAULT '', location_label TEXT NOT NULL,
 lat REAL, lng REAL, status TEXT DEFAULT 'pending',
 partner_id INTEGER, quoted_amount INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(customer_id) REFERENCES users(id), FOREIGN KEY(partner_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS earnings (
 id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL UNIQUE,
 partner_id INTEGER NOT NULL, amount INTEGER NOT NULL, payment_status TEXT DEFAULT 'unpaid',
 paid_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
`);
const adminEmail = (process.env.ADMIN_EMAIL || "admin@bikeresq.local").toLowerCase();
const adminPassword = process.env.ADMIN_PASSWORD || "ChangeThisAdminPassword123!";
const adminExists = db.prepare("SELECT id FROM users WHERE email=?").get(adminEmail);
if (!adminExists) {
  const hash = bcrypt.hashSync(adminPassword, 12);
  db.prepare("INSERT INTO users(name,phone,email,password_hash,role) VALUES(?,?,?,?,?)")
    .run("BIKE RESQ Admin", "0000000000", adminEmail, hash, "admin");
  console.log(`Admin created: ${adminEmail} (change password in .env before real use)`);
}
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: "30kb" }));
app.use(express.urlencoded({ extended: false }));
app.use(session({
  name: "bike_resq_sid",
  secret: process.env.SESSION_SECRET || "local-development-secret-change-me",
  resave: false, saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: "lax", secure: false, maxAge: 8*60*60*1000 }
}));
app.use("/api/", rateLimit({ windowMs: 15*60*1000, limit: 180 }));
app.use(express.static(path.join(__dirname, "public")));

const clean = v => String(v ?? "").trim();
const safeUser = u => ({ id:u.id, name:u.name, email:u.email, role:u.role, phone:u.phone, service:u.service, area:u.area, phonepe_note:u.phonepe_note });
function auth(req,res,next){ if(!req.session.user) return res.status(401).json({error:"Please log in first."}); next(); }
function roles(...allowed){ return (req,res,next)=>{ if(!req.session.user || !allowed.includes(req.session.user.role)) return res.status(403).json({error:"Not authorised."}); next(); }; }
function refreshUser(req){ req.session.user = safeUser(db.prepare("SELECT * FROM users WHERE id=?").get(req.session.user.id)); }

app.get("/api/me",(req,res)=>res.json({user:req.session.user||null}));
app.post("/api/register",(req,res)=>{
 const name=clean(req.body.name), phone=clean(req.body.phone), email=clean(req.body.email).toLowerCase();
 const password=String(req.body.password||""), role=clean(req.body.role), service=clean(req.body.service), area=clean(req.body.area);
 if(!name || !/^[0-9]{10}$/.test(phone) || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || password.length<10 || !["customer","partner"].includes(role))
  return res.status(400).json({error:"Enter a name, valid 10-digit phone, email, password (10+ characters), and valid account type."});
 if(role==="partner" && (!service || !area)) return res.status(400).json({error:"Partners must select a service and service area."});
 try{
  const hash=bcrypt.hashSync(password,12);
  const info=db.prepare("INSERT INTO users(name,phone,email,password_hash,role,service,area) VALUES(?,?,?,?,?,?,?)").run(name,phone,email,hash,role,service,area);
  const u=safeUser(db.prepare("SELECT * FROM users WHERE id=?").get(info.lastInsertRowid));
  req.session.user=u; res.json({user:u});
 }catch(e){res.status(409).json({error:"That email is already registered."});}
});
app.post("/api/login",(req,res)=>{
 const email=clean(req.body.email).toLowerCase(), password=String(req.body.password||"");
 const u=db.prepare("SELECT * FROM users WHERE email=?").get(email);
 if(!u || !bcrypt.compareSync(password,u.password_hash)) return res.status(401).json({error:"Incorrect email or password."});
 req.session.user=safeUser(u); res.json({user:req.session.user});
});
app.post("/api/logout",(req,res)=>req.session.destroy(()=>res.json({ok:true})));

app.post("/api/requests",auth,roles("customer"),(req,res)=>{
 const service=clean(req.body.service), details=clean(req.body.details).slice(0,500);
 const location=clean(req.body.location).slice(0,180);
 const lat=Number(req.body.lat), lng=Number(req.body.lng);
 const allowed=["mechanic","puncture","towing","battery","petrol_referral","diesel_referral"];
 if(!allowed.includes(service) || !location) return res.status(400).json({error:"Choose a service and confirm a location."});
 if(!Number.isFinite(lat)||!Number.isFinite(lng)||Math.abs(lat)>90||Math.abs(lng)>180) return res.status(400).json({error:"Please share your location using the location button."});
 // Fuel options are referral-only: no fuel transport, storage, dispatch or delivery workflow.
 const info=db.prepare("INSERT INTO requests(customer_id,service,details,location_label,lat,lng) VALUES(?,?,?,?,?,?)")
 .run(req.session.user.id,service,details,location,lat,lng);
 res.json({id:info.lastInsertRowid,message:"Request created. A provider must be assigned by an administrator."});
});
app.get("/api/my-requests",auth,(req,res)=>{
 let rows;
 if(req.session.user.role==="customer") rows=db.prepare("SELECT r.*, u.name AS partner_name FROM requests r LEFT JOIN users u ON u.id=r.partner_id WHERE r.customer_id=? ORDER BY r.id DESC").all(req.session.user.id);
 else if(req.session.user.role==="partner") rows=db.prepare("SELECT r.*, u.name AS customer_name FROM requests r JOIN users u ON u.id=r.customer_id WHERE r.partner_id=? ORDER BY r.id DESC").all(req.session.user.id);
 else rows=db.prepare("SELECT r.*, c.name AS customer_name, p.name AS partner_name FROM requests r JOIN users c ON c.id=r.customer_id LEFT JOIN users p ON p.id=r.partner_id ORDER BY r.id DESC").all();
 res.json({requests:rows});
});
app.get("/api/partner-requests",auth,roles("partner"),(req,res)=>{
 const rows=db.prepare("SELECT r.*,u.name AS customer_name,u.phone AS customer_phone FROM requests r JOIN users u ON u.id=r.customer_id WHERE r.status='assigned' AND r.partner_id=? ORDER BY r.id DESC").all(req.session.user.id);
 res.json({requests:rows});
});
app.post("/api/partner-requests/:id/status",auth,roles("partner"),(req,res)=>{
 const status=clean(req.body.status);
 if(!["accepted","in_progress","completed"].includes(status)) return res.status(400).json({error:"Invalid status."});
 const r=db.prepare("SELECT * FROM requests WHERE id=? AND partner_id=?").get(req.params.id,req.session.user.id);
 if(!r) return res.status(404).json({error:"Request not found."});
 const transitions={assigned:["accepted"],accepted:["in_progress"],in_progress:["completed"]};
 if(!transitions[r.status]?.includes(status)) return res.status(400).json({error:"That status change is not allowed."});
 db.prepare("UPDATE requests SET status=? WHERE id=?").run(status,r.id);
 if(status==="completed") db.prepare("INSERT OR IGNORE INTO earnings(request_id,partner_id,amount) VALUES(?,?,?)").run(r.id,req.session.user.id,Math.max(0,Number(r.quoted_amount)||0));
 res.json({ok:true});
});
app.get("/api/earnings",auth,roles("partner"),(req,res)=>{
 const rows=db.prepare("SELECT e.*,r.service FROM earnings e JOIN requests r ON r.id=e.request_id WHERE e.partner_id=? ORDER BY e.id DESC").all(req.session.user.id);
 const total=rows.reduce((n,x)=>n+x.amount,0), paid=rows.filter(x=>x.payment_status==="paid").reduce((n,x)=>n+x.amount,0);
 res.json({earnings:rows,total,paid,unpaid:total-paid});
});
app.put("/api/partner/payment-info",auth,roles("partner"),(req,res)=>{
 const note=clean(req.body.phonepe_note).slice(0,100);
 db.prepare("UPDATE users SET phonepe_note=? WHERE id=?").run(note,req.session.user.id); refreshUser(req); res.json({user:req.session.user});
});
app.get("/api/admin/summary",auth,roles("admin"),(req,res)=>{
 const users=db.prepare("SELECT id,name,email,phone,role,service,area,phonepe_note FROM users WHERE role IN ('customer','partner') ORDER BY id DESC").all();
 const requests=db.prepare("SELECT r.*,c.name AS customer_name,c.phone AS customer_phone,p.name AS partner_name FROM requests r JOIN users c ON c.id=r.customer_id LEFT JOIN users p ON p.id=r.partner_id ORDER BY r.id DESC").all();
 res.json({users,requests});
});
app.post("/api/admin/assign",auth,roles("admin"),(req,res)=>{
 const requestId=Number(req.body.requestId), partnerId=Number(req.body.partnerId), amount=Math.max(0,Math.round(Number(req.body.amount)||0));
 const p=db.prepare("SELECT id FROM users WHERE id=? AND role='partner'").get(partnerId);
 const r=db.prepare("SELECT id,status FROM requests WHERE id=?").get(requestId);
 if(!p||!r||!["pending"].includes(r.status)) return res.status(400).json({error:"Select a pending request and valid partner."});
 db.prepare("UPDATE requests SET partner_id=?,quoted_amount=?,status='assigned' WHERE id=?").run(partnerId,amount,requestId);
 res.json({ok:true});
});
app.post("/api/admin/mark-paid",auth,roles("admin"),(req,res)=>{
 const id=Number(req.body.earningId);
 const info=db.prepare("UPDATE earnings SET payment_status='paid',paid_at=CURRENT_TIMESTAMP WHERE id=? AND payment_status='unpaid'").run(id);
 if(!info.changes) return res.status(404).json({error:"Unpaid earning not found."});
 res.json({ok:true});
});
app.use((err,req,res,next)=>{console.error(err);res.status(500).json({error:"Server error."});});
app.listen(PORT,()=>console.log(`BIKE RESQ running at http://localhost:${PORT}`));
