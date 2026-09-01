"use client";

import { useState } from "react";
import { ArrowRight, BookOpenCheck, BrainCircuit, ChevronRight, Database, FileSearch, Gauge, Link2, Menu, Network, Pickaxe, Quote, SearchCheck, ShieldCheck, Target, Users, X } from "lucide-react";

const audiences = [
  { label: "Mantenimiento", title: "Menos tiempo buscando. Más tiempo resolviendo.", text: "Acceda rápidamente a antecedentes de fallas, intervenciones, repuestos y recomendaciones técnicas vinculadas a cada activo.", outcome: "Agiliza el diagnóstico y la preparación de intervenciones.", icon: Gauge },
  { label: "Operaciones", title: "Conocimiento disponible cuando la continuidad lo exige.", text: "Transforme la historia del activo en información accesible para responder mejor ante eventos que afectan la producción.", outcome: "Apoya decisiones orientadas a disponibilidad y continuidad operacional.", icon: Pickaxe },
  { label: "Confiabilidad", title: "Una base común para RCA, FMECA y mejora continua.", text: "Relacione modos de falla, causas, intervenciones y documentación técnica en una memoria trazable y auditable.", outcome: "Acelera análisis y conserva las lecciones aprendidas.", icon: Target },
];
const process = [
  { n: "01", title: "Reunir", text: "SAP PM, FMECA, manuales OEM, RCA, procedimientos e históricos.", icon: Database },
  { n: "02", title: "Organizar", text: "Clasificar la información por activo, componente, falla, repuesto y contexto.", icon: Network },
  { n: "03", title: "Conectar", text: "Relacionar antecedentes dispersos y conocimiento técnico relevante.", icon: Link2 },
  { n: "04", title: "Validar", text: "Entregar respuestas con fuentes verificables y revisión del especialista.", icon: ShieldCheck },
];
const results = [
  { title: "Reducción", subtitle: "del tiempo de análisis", text: "Menos horas reconstruyendo antecedentes antes de diagnosticar o intervenir.", icon: Gauge },
  { title: "Orden", subtitle: "de la información técnica", text: "Una consulta común para fuentes que hoy viven en sistemas, documentos y planillas.", icon: SearchCheck },
  { title: "Conocimiento", subtitle: "que permanece", text: "Las experiencias y lecciones de especialistas quedan disponibles para la organización.", icon: BrainCircuit },
];

function Brand() {
  return <span className="brand"><img className="brand-logo" src="/monitoring-logo-horizontal.svg" alt="Monitoring Gestión de Activos"/><span className="product-tag">MMI</span></span>;
}

export default function Home() {
  const [activeAudience, setActiveAudience] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const active = audiences[activeAudience];
  const ActiveIcon = active.icon;
  return (
    <main>
      <header className="site-header">
        <a href="#inicio" aria-label="MMI by Monitoring, inicio"><Brand /></a>
        <button className="menu-button" onClick={() => setMenuOpen(!menuOpen)} aria-label="Abrir navegación" aria-expanded={menuOpen}>{menuOpen ? <X/> : <Menu/>}</button>
        <nav className={menuOpen ? "nav open" : "nav"} aria-label="Navegación principal">
          <a href="#solucion" onClick={() => setMenuOpen(false)}>Solución</a><a href="#proceso" onClick={() => setMenuOpen(false)}>Proceso</a><a href="#impacto" onClick={() => setMenuOpen(false)}>Resultados</a>
          <a href="#demostracion" className="nav-cta" onClick={() => setMenuOpen(false)}>Solicitar demostración <ArrowRight size={16}/></a>
        </nav>
      </header>

      <section className="hero" id="inicio">
        <div className="hero-grid" aria-hidden="true"/>
        <div className="hero-content">
          <div className="eyebrow"><span/> Inteligencia para mantenimiento minero</div>
          <h1>La memoria técnica<br/>inteligente de <em>sus activos.</em></h1>
          <p className="hero-lead">Conecte SAP PM, FMECA, manuales e historial de mantenimiento para transformar información dispersa en conocimiento operativo respaldado por evidencia.</p>
          <div className="hero-actions"><a className="button primary" href="#demostracion">Ver cómo funciona <ArrowRight size={18}/></a><a className="button secondary" href="#solucion">Explorar la solución</a></div>
          <div className="hero-proof"><span><ShieldCheck/> No reemplaza SAP</span><span><Users/> Validación humana</span><span><BookOpenCheck/> Evidencia trazable</span></div>
        </div>
        <div className="hero-visual" aria-label="Fuentes técnicas conectadas por MMI">
          <div className="orbit orbit-one"/><div className="orbit orbit-two"/>
          <div className="core"><img src="/monitoring-logo-circular.svg" alt="Símbolo original de Monitoring"/><strong>MMI</strong><span>Memoria técnica viva</span></div>
          <div className="source source-a"><Database/><span>SAP PM</span></div><div className="source source-b"><FileSearch/><span>FMECA</span></div><div className="source source-c"><BookOpenCheck/><span>Manuales OEM</span></div><div className="source source-d"><Users/><span>Experiencia</span></div>
        </div>
      </section>

      <section className="problem section" id="solucion">
        <div className="section-label">01 · El desafío</div>
        <div className="problem-layout"><h2>Su planta ya tiene los datos.<br/><span>MMI los convierte en conocimiento.</span></h2><div className="problem-copy"><p>La información crítica de un activo suele estar distribuida entre sistemas, documentos y personas. El desafío no es solo encontrar un archivo: es relacionar su contenido, validar el origen y convertirlo en una respuesta útil.</p><blockquote><Quote/> ¿Cuánto conocimiento de sus activos está almacenado, pero no realmente disponible cuando se necesita?</blockquote></div></div>
      </section>

      <section className="audience section">
        <div className="section-heading"><div className="section-label">02 · Valor para cada área</div><h2>Una solución. Tres perspectivas críticas.</h2></div>
        <div className="audience-tabs" role="tablist">{audiences.map((item,index)=><button key={item.label} role="tab" aria-selected={activeAudience===index} className={activeAudience===index?"active":""} onClick={()=>setActiveAudience(index)}><item.icon/> {item.label}</button>)}</div>
        <div className="audience-panel" role="tabpanel"><div className="panel-icon"><ActiveIcon/></div><div><span className="panel-kicker">Para gerencia de {active.label.toLowerCase()}</span><h3>{active.title}</h3><p>{active.text}</p></div><div className="panel-result"><span>Resultado esperado</span><strong>{active.outcome}</strong></div></div>
      </section>

      <section className="process-section" id="proceso"><div className="section process-inner">
        <div className="section-heading light"><div className="section-label">03 · El proceso</div><h2>Del dato disperso a una respuesta confiable.</h2><p>Un proceso progresivo, desacoplado y enfocado en el conocimiento que genera valor para la operación.</p></div>
        <div className="process-grid">{process.map((step,i)=><article className="process-card" key={step.n}><div className="process-top"><span>{step.n}</span><step.icon/></div><h3>{step.title}</h3><p>{step.text}</p>{i<3&&<ChevronRight className="process-arrow"/>}</article>)}</div>
        <div className="process-note"><ShieldCheck/><div><strong>Seguridad operacional primero</strong><span>MMI recomienda y entrega evidencia. La evaluación y autorización final permanece en manos del especialista.</span></div></div>
      </div></section>

      <section className="results section" id="impacto">
        <div className="section-heading centered"><div className="section-label">04 · El impacto</div><h2>Resultados que la operación puede comprobar.</h2><p>El valor no se mide por instalar tecnología, sino por mejorar la forma en que el equipo accede, conecta y utiliza su conocimiento.</p></div>
        <div className="results-grid">{results.map(result=><article className="result-card" key={result.title}><div className="result-icon"><result.icon/></div><h3>{result.title}</h3><span>{result.subtitle}</span><p>{result.text}</p></article>)}</div>
        <div className="metrics-strip"><div><strong>Tiempo</strong><span>para localizar antecedentes</span></div><div><strong>Fuentes</strong><span>conectadas por activo</span></div><div><strong>Evidencia</strong><span>en cada respuesta</span></div><div><strong>Conocimiento</strong><span>experto capturado</span></div></div>
      </section>

      <section className="demo section" id="demostracion"><div className="demo-card">
        <div className="demo-copy"><div className="eyebrow"><span/> Demostración con un caso real</div><h2>Active la memoria técnica de un activo crítico.</h2><p>Seleccione un equipo y una problemática de su operación. Mostraremos cómo MMI puede recuperar, relacionar y presentar el conocimiento disponible con evidencia trazable.</p><a className="button primary" href="mailto:contacto@monitoring.cl?subject=Demostración%20MMI%20by%20Monitoring">Solicitar una demostración <ArrowRight size={18}/></a></div>
        <div className="demo-example"><div className="example-label"><span/> Ejemplo de consulta</div><p>“¿Qué modos de falla se han repetido en esta bomba y qué acciones recomienda el FMECA vigente?”</p><div className="example-response"><SearchCheck/><span>MMI conecta el historial, el FMECA y la documentación técnica para responder con fuentes verificables.</span></div></div>
      </div></section>

      <footer><Brand/><p>Monitoring Maintenance Intelligence</p><a href="https://www.monitoring.cl">monitoring.cl <ArrowRight size={15}/></a></footer>
    </main>
  );
}
