"use client";

import { useEffect, useState } from "react";
import {
  Activity, AlertTriangle, ArrowRight, BookOpen, Boxes, Check, CheckCircle2,
  ChevronRight, ClipboardCheck, Database, FileClock, FileSearch, Gauge, History,
  LayoutDashboard, Library, ListChecks, LoaderCircle, Menu, Network, PanelLeftClose,
  Search, Settings, ShieldCheck, Terminal, Upload, UserCircle2, Wrench, X
} from "lucide-react";

type View = "overview" | "loading" | "diagnostic" | "final";

const navItems = [
  { id: "diagnostic", label: "Diagnóstico", icon: Activity },
  { id: "overview", label: "Activos", icon: Boxes },
  { id: "documents", label: "Documentos", icon: FileSearch },
  { id: "trace", label: "Trazabilidad", icon: Network },
  { id: "logs", label: "Registros", icon: Terminal },
];

const facts = [
  ["Temperatura del cojinete de empuje TE-401A alcanzó 98 °C (límite: 95 °C)", "Manual OEM GE · Vol. 2 · p. 112"],
  ["Vibración radial VE-402X registró 5,2 mm/s RMS, con 1X RPM dominante", "Manual OEM GE · Vol. 3 · p. 45"],
  ["Flujo de aceite lubricante FT-405 cayó a 120 L/min (nominal: 150)", "P&ID Lubricación · Rev. 4"],
];

const hypotheses = [
  { code: "H1", title: "Desalineamiento térmico rotor–estator", confidence: "92%", tone: "good", text: "La firma vibratoria 1X RPM y el aumento térmico del cojinete sugieren expansión asimétrica y pérdida de alineamiento." },
  { code: "H2", title: "Falla en suministro de aceite lubricante", confidence: "68%", tone: "warn", text: "La reducción de caudal explica la temperatura elevada; la vibración podría ser una consecuencia secundaria del aumento de fricción." },
];

const checklist = [
  "Verificar nivel y presión en el tanque de lubricación principal LSH-400.",
  "Tomar muestra de aceite para análisis tribológico urgente, código ISO 4406.",
  "Inspeccionar termocupla TE-401A por falsos contactos o degradación de vaina.",
];

const assets = [
  { name: "Molino SAG-01", code: "ML-SAG-01", health: 94, state: "Normal", tone: "good", metric: "Disponibilidad", value: "97,8%", trend: "+1,2%" },
  { name: "Chancador primario", code: "CH-PRI-02", health: 72, state: "Atención", tone: "warn", metric: "Vibración", value: "4,8 mm/s", trend: "+14%" },
  { name: "Turbina de servicio", code: "STG-01-X", health: 61, state: "Diagnóstico", tone: "danger", metric: "Temperatura", value: "98 °C", trend: "+8 °C" },
];

function Header({ onMenu }: { onMenu: () => void }) {
  return <header className="topbar">
    <div className="top-left">
      <button className="mobile-menu" onClick={onMenu} aria-label="Abrir menú"><Menu /></button>
      <img src="/monitoring-logo-horizontal.svg" className="corp-logo" alt="Monitoring Gestión de Activos" />
      <span className="mmi-label">MMI</span>
      <span className="top-divider" />
      <span className="layer-label">Capa de inteligencia operacional</span>
    </div>
    <div className="top-right">
      <span className="security-chip"><i /> RLS activo</span>
      <span className="security-chip wide"><i /> Zero-data retention</span>
      <span className="site-name">Faena Minera Centinela</span>
      <button aria-label="Configuración"><Settings /></button><button aria-label="Perfil"><UserCircle2 /></button>
    </div>
  </header>;
}

function Sidebar({ view, open, close, select }: { view: View; open: boolean; close: () => void; select: (id: string) => void }) {
  return <aside className={`sidebar ${open ? "open" : ""}`}>
    <button className="sidebar-close" onClick={close}><X /></button>
    <div className="profile"><div className="profile-mark"><Wrench /></div><div><strong>Plant Manager</strong><span>Centinela Site</span></div></div>
    <nav>{navItems.map(item => <button key={item.id} className={(item.id === view || (item.id === "diagnostic" && ["loading","final"].includes(view))) ? "active" : ""} onClick={() => select(item.id)}><item.icon /> <span>{item.label}</span>{item.id === "diagnostic" && <i className="live-dot"/>}</button>)}</nav>
    <div className="side-status"><span>Estado del sistema</span><strong><i/> Todos los servicios operativos</strong></div>
    <div className="side-foot"><ShieldCheck/><span>Validación humana obligatoria</span></div>
  </aside>;
}

function SearchBar({ query, setQuery, analyze }: { query: string; setQuery: (v:string)=>void; analyze:()=>void }) {
  return <section className="search-panel">
    <div className="search-main"><label>Consultar motor MMI</label><div className="search-input"><Search/><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&analyze()} placeholder="Escribe una falla, código, síntoma o activo..." /></div></div>
    <div className="select-field"><label>Activo</label><select><option>STG-01-X</option><option>ML-SAG-01</option></select></div>
    <div className="select-field"><label>Vigencia</label><select><option>Últimas 24 h</option><option>7 días</option></select></div>
    <button className="analyze-btn" onClick={analyze}>Analizar <ArrowRight /></button>
  </section>;
}

function Overview({ analyze }: { analyze: (q?:string)=>void }) {
  const [q,setQ]=useState("");
  return <div className="view">
    <div className="page-head"><div><span className="eyebrow">Resumen operacional</span><h1>Estado de la planta</h1><p>Visión consolidada del comportamiento y riesgo de activos críticos.</p></div><div className="updated"><i/> Datos actualizados hace 2 min</div></div>
    <SearchBar query={q} setQuery={setQ} analyze={()=>analyze(q)} />
    <div className="kpi-grid">
      <article><div className="kpi-icon blue"><Gauge/></div><span>Disponibilidad global</span><strong>96,4%</strong><small className="positive">+0,8% vs. mes anterior</small></article>
      <article><div className="kpi-icon green"><CheckCircle2/></div><span>Activos saludables</span><strong>42 / 48</strong><small>87,5% de la flota crítica</small></article>
      <article><div className="kpi-icon orange"><AlertTriangle/></div><span>Alertas activas</span><strong>6</strong><small className="attention">2 requieren evaluación</small></article>
      <article><div className="kpi-icon violet"><Database/></div><span>Fuentes conectadas</span><strong>1.284</strong><small>SAP · OEM · RCA · FMECA</small></article>
    </div>
    <div className="section-row"><div><span className="eyebrow">Activos priorizados</span><h2>Condición y señales relevantes</h2></div><button>Ver todos <ChevronRight/></button></div>
    <div className="asset-grid">{assets.map(a=><article className="asset-card" key={a.code}>
      <div className="asset-top"><div className="asset-symbol"><Activity/></div><div><strong>{a.name}</strong><span>{a.code}</span></div><em className={a.tone}>{a.state}</em></div>
      <div className="health"><div><span>Índice de salud</span><b>{a.health}%</b></div><div className="health-bar"><i className={a.tone} style={{width:`${a.health}%`}}/></div></div>
      <div className="asset-metric"><span>{a.metric}</span><strong>{a.value}</strong><small className={a.tone}>{a.trend}</small></div>
      <button onClick={()=>analyze(`Analizar ${a.name} ${a.code}`)}>Abrir diagnóstico <ArrowRight/></button>
    </article>)}</div>
  </div>;
}

function LoadingView() {
  const [progress,setProgress]=useState(12);
  useEffect(()=>{const t=setInterval(()=>setProgress(p=>Math.min(94,p+7)),140);return()=>clearInterval(t)},[]);
  const phases=[["01","Normalización de datos","completed"],["02","Recuperación híbrida RAG","completed"],["03","Contraste de evidencia","active"],["04","Síntesis prescriptiva","pending"]];
  return <div className="loading-view"><div className="loading-grid"/><div className="loading-content">
    <div className="loader-orb"><img src="/monitoring-logo-circular.svg" alt="Monitoring"/><LoaderCircle/></div>
    <span className="eyebrow">MMI · Motor de análisis</span><h1>Construyendo diagnóstico asistido</h1><p>Conectando historial del activo, manuales OEM y análisis de confiabilidad.</p>
    <div className="phase-grid">{phases.map(p=><article className={p[2]} key={p[0]}><span>{p[0]}</span><div><strong>{p[1]}</strong><small>{p[2]==="completed"?"Completado":p[2]==="active"?"Procesando fuentes y conflictos":"En espera"}</small></div>{p[2]==="completed"?<Check/>:p[2]==="active"?<LoaderCircle className="spin"/>:<i/>}</article>)}</div>
    <div className="progress"><div><span>Progreso general</span><b>{progress}%</b></div><div className="progress-bar"><i style={{width:`${progress}%`}}/></div></div>
    <div className="terminal-line"><Terminal/><code>RAG/HYBRID · evidence_validation=true · human_gate=required</code></div>
  </div></div>;
}

function Diagnostic({ validate, rerun }: { validate:()=>void; rerun:()=>void }) {
  const [checked,setChecked]=useState<boolean[]>([false,false,false]);
  return <div className="view diagnostic-view">
    <SearchBar query="Alta temperatura y vibración en turbina STG-01-X" setQuery={()=>{}} analyze={rerun}/>
    <div className="result-head"><div><span className="eyebrow">Análisis generado</span><h1>Diagnóstico del síntoma</h1></div><div className="result-badges"><span className="supported"><i/> Evidencia soportada</span><span><ShieldCheck/> Confianza alta · 92%</span></div></div>
    <div className="workspace-grid"><div className="workspace-main">
      <section className="tech-card success"><header><div><ClipboardCheck/><h2>Hechos verificados</h2></div><span>Datos + documentos</span></header><div className="fact-list">{facts.map((f,i)=><div key={i}><p>{f[0]}</p><code>{f[1]}</code></div>)}</div></section>
      <section className="tech-card hypothesis"><header><div><Activity/><h2>Hipótesis del sistema</h2></div></header><div className="ai-warning"><AlertTriangle/> Inferencia IA: requiere criterio del especialista</div><div className="hypothesis-list">{hypotheses.map(h=><article key={h.code}><b>{h.code}</b><div><h3>{h.title}</h3><p>{h.text}</p></div><strong className={h.tone}>{h.confidence}</strong></article>)}</div></section>
      <section className="tech-card checklist"><header><div><ListChecks/><h2>Verificación física</h2></div><button>Exportar PDF</button></header><div>{checklist.map((item,i)=><label key={item}><input type="checkbox" checked={checked[i]} onChange={()=>setChecked(c=>c.map((v,j)=>j===i?!v:v))}/><span>{item}</span></label>)}</div></section>
    </div><aside className="evidence-panel"><header><Library/><h2>Fuentes y evidencia</h2></header>
      <article><div><BookOpen/><strong>Manual OEM GE Frame 6B</strong><small>Vol. 2 · p. 112</small></div><code>SECCIÓN 4.2.1 COJINETES<br/>MAX TEMP: 90 °C<br/>ALARMA: 95 °C<br/><em>Acción: inspeccionar flujo si supera 95 °C.</em></code></article>
      <article><div><History/><strong>Histórico EAM / CMMS</strong><small>WO-88912</small></div><code>FECHA: 2023-04-12<br/>Reemplazo de rodamiento similar.<br/>CAUSA: contaminación de aceite.<br/><em>MTBF: 8.400 h / esperado: 12.000 h.</em></code></article>
      <div className="conflict"><AlertTriangle/><div><strong>Discrepancia detectada</strong><p>El sensor PT-882 fue calibrado hace más de 365 días. La lectura podría variar ±5%.</p></div></div>
    </aside></div>
    <div className="action-bar"><button onClick={rerun}>Descartar</button><button className="preload"><Upload/> Precargar EAM/CMMS</button><button className="validate" onClick={validate}><CheckCircle2/> Validar diagnóstico</button></div>
  </div>;
}

function FinalView({ back }: { back:()=>void }) {
  return <div className="view final-view">
    <div className="page-head"><div><span className="eyebrow">Diagnóstico validado</span><h1>Resultado técnico final</h1><p>La recomendación fue revisada y autorizada por el responsable técnico.</p></div><span className="certificate-status"><ShieldCheck/> Validación humana completada</span></div>
    <div className="final-grid"><article className="certificate"><img src="/monitoring-logo-circular.svg" alt="Monitoring"/><span>Certificado de evidencia</span><strong>MMI-2026-00928</strong><div><b>92%</b><small>Confianza consolidada</small></div><p>Emitido para STG-01-X<br/>01 septiembre 2026 · 00:15 UTC</p></article>
      <section className="validated-findings"><header><CheckCircle2/><div><span>Conclusión validada</span><h2>Desalineamiento térmico con degradación del sistema de lubricación</h2></div></header><p>La evidencia documental y operacional sostiene una relación entre el bajo caudal de lubricación, el aumento térmico y la firma vibratoria 1X RPM.</p><div className="recommendation"><Wrench/><div><strong>Acción recomendada</strong><p>Inspeccionar el circuito de lubricación, verificar alineamiento en condición térmica y ejecutar análisis de aceite antes del próximo ciclo.</p></div></div><div className="signoff"><div><span>Validado por</span><strong>Supervisor de Confiabilidad</strong></div><div><span>Estado</span><strong className="good">Autorizado para planificación</strong></div></div></section>
    </div>
    <section className="trace-log"><header><FileClock/><h2>Registro de trazabilidad</h2></header><code>00:12:14 · consulta registrada · STG-01-X<br/>00:12:18 · 1.284 fuentes indexadas · 7 fuentes recuperadas<br/>00:12:21 · evidencia CoVe: SUPPORTED · confianza 0.92<br/>00:15:03 · validación humana registrada · estado FINAL</code></section>
    <button className="back-overview" onClick={back}>Volver al panel <ArrowRight/></button>
  </div>;
}

export default function Home(){
  const [view,setView]=useState<View>("overview"); const [menu,setMenu]=useState(false);
  const analyze=()=>{setView("loading");window.setTimeout(()=>setView("diagnostic"),1800)};
  const select=(id:string)=>{setMenu(false);if(id==="overview")setView("overview");else if(id==="diagnostic")setView("diagnostic")};
  return <main className="app-shell"><Header onMenu={()=>setMenu(true)}/><Sidebar view={view} open={menu} close={()=>setMenu(false)} select={select}/><section className="app-content">{view==="overview"&&<Overview analyze={analyze}/>} {view==="loading"&&<LoadingView/>} {view==="diagnostic"&&<Diagnostic rerun={analyze} validate={()=>setView("final")}/>} {view==="final"&&<FinalView back={()=>setView("overview")}/>}</section>{menu&&<button className="overlay" onClick={()=>setMenu(false)} aria-label="Cerrar menú"/>}</main>
}
