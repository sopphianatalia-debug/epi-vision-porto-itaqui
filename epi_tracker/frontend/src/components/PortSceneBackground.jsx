import React from "react";

// Cena decorativa de fundo (SVG, desenhado a mao, nao e uma foto) --
// puramente ilustrativo, aria-hidden. As posicoes dos elementos de dados
// reais em AreasMap.jsx foram escolhidas para coincidir com as zonas
// desenhadas aqui (agua/cais em cima, patio de conteineres a esquerda,
// area de carga ao centro, armazem/oficina a direita, portaria/caminhoes
// mais a esquerda embaixo, administrativa/abastecimento/obras/restrita na
// faixa inferior) -- viewBox 0 0 1200 900.
export function PortSceneBackground() {
  const containerColors = ["#c0392b", "#2980b9", "#f39c12", "#27ae60", "#8e44ad", "#16a085"];

  return (
    <svg viewBox="0 0 1200 900" preserveAspectRatio="none" aria-hidden="true"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" }}>
      <defs>
        <linearGradient id="water" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2f6fa8" />
          <stop offset="100%" stopColor="#4a8fc7" />
        </linearGradient>
        <linearGradient id="yard" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c7ccd3" />
          <stop offset="100%" stopColor="#b8bec7" />
        </linearGradient>
      </defs>

      {/* Agua */}
      <rect x="0" y="0" width="1200" height="195" fill="url(#water)" />
      <g opacity="0.18" stroke="#ffffff" strokeWidth="2">
        <path d="M0 40 Q60 30 120 40 T240 40" fill="none" />
        <path d="M900 60 Q960 50 1020 60 T1140 60" fill="none" />
        <path d="M0 130 Q60 120 120 130 T240 130" fill="none" />
      </g>

      {/* Navio */}
      <g transform="translate(330,55)">
        <rect x="0" y="30" width="420" height="70" rx="8" fill="#2c3e50" />
        <polygon points="0,30 -25,65 0,100" fill="#2c3e50" />
        <rect x="370" y="0" width="40" height="30" fill="#34495e" />
        {Array.from({ length: 9 }).map((_, col) =>
          Array.from({ length: 3 }).map((_, row) => (
            <rect key={`${col}-${row}`} x={20 + col * 40} y={38 + row * 15} width="34" height="12"
              fill={containerColors[(col + row) % containerColors.length]} />
          ))
        )}
      </g>

      {/* Guindastes do cais */}
      {[420, 880].map((cx) => (
        <g key={cx} stroke="#e0a527" strokeWidth="5" fill="none">
          <line x1={cx} y1="195" x2={cx} y2="30" />
          <line x1={cx - 60} y1="45" x2={cx + 90} y2="45" />
          <line x1={cx} y1="30" x2={cx - 60} y2="45" />
          <line x1={cx} y1="30" x2={cx + 90} y2="45" />
        </g>
      ))}

      {/* Faixa do cais (asfalto) */}
      <rect x="0" y="195" width="1200" height="45" fill="#8b95a1" />
      <line x1="0" y1="217" x2="1200" y2="217" stroke="#e8e8e8" strokeWidth="2" strokeDasharray="14 10" />

      {/* Patio operacional (fundo) */}
      <rect x="0" y="240" width="1200" height="660" fill="url(#yard)" />

      {/* Vias internas -- perimetro + cruzamentos */}
      <g fill="none" stroke="#9098a3" strokeWidth="26">
        <path d="M40 260 L40 860 L1160 860 L1160 260" />
        <line x1="270" y1="260" x2="270" y2="860" />
        <line x1="660" y1="260" x2="660" y2="860" />
        <line x1="990" y1="260" x2="990" y2="860" />
        <line x1="40" y1="640" x2="1160" y2="640" />
      </g>
      <g fill="none" stroke="#e8e8e8" strokeWidth="2" strokeDasharray="16 12" opacity="0.7">
        <path d="M40 260 L40 860 L1160 860 L1160 260" />
        <line x1="270" y1="260" x2="270" y2="860" />
        <line x1="660" y1="260" x2="660" y2="860" />
        <line x1="990" y1="260" x2="990" y2="860" />
        <line x1="40" y1="640" x2="1160" y2="640" />
      </g>

      {/* Patio de armazenagem -- fileiras de conteineres (decorativo) */}
      <g>
        {Array.from({ length: 5 }).map((_, row) =>
          Array.from({ length: 6 }).map((_, col) => (
            <rect key={`c-${row}-${col}`} x={300 + col * 55} y={300 + row * 55} width="46" height="42" rx="3"
              fill={containerColors[(row + col) % containerColors.length]} opacity="0.85" />
          ))
        )}
      </g>

      {/* Area de carga/descarga -- guindastes laranja (decorativo) */}
      <g stroke="#c9600f" strokeWidth="6" fill="none">
        <line x1="770" y1="600" x2="770" y2="330" />
        <line x1="770" y1="330" x2="900" y2="330" />
        <line x1="900" y1="330" x2="900" y2="600" />
        <line x1="700" y1="380" x2="960" y2="380" />
      </g>
      <g>
        {Array.from({ length: 3 }).map((_, row) =>
          Array.from({ length: 4 }).map((_, col) => (
            <rect key={`d-${row}-${col}`} x={720 + col * 50} y={480 + row * 45} width="42" height="36" rx="3"
              fill={containerColors[(row + col + 2) % containerColors.length]} opacity="0.8" />
          ))
        )}
      </g>

      {/* Armazem (telhado azul) */}
      <rect x="1010" y="270" width="150" height="140" rx="6" fill="#4a6fa5" opacity="0.85" />
      <line x1="1010" y1="300" x2="1160" y2="300" stroke="#3a5680" strokeWidth="3" />

      {/* Oficina */}
      <rect x="1010" y="460" width="150" height="110" rx="6" fill="#6b7280" opacity="0.75" />

      {/* Patio de caminhoes */}
      <rect x="70" y="460" width="180" height="110" rx="6" fill="#9098a3" opacity="0.5" />

      {/* Portaria */}
      <rect x="70" y="290" width="180" height="120" rx="6" fill="#5c8a6a" opacity="0.5" />

      {/* Predio administrativo */}
      <rect x="300" y="670" width="140" height="90" rx="6" fill="#8a94a6" opacity="0.6" />

      {/* Tanques de abastecimento */}
      <circle cx="600" cy="700" r="30" fill="#9098a3" opacity="0.6" />
      <circle cx="650" cy="710" r="24" fill="#9098a3" opacity="0.6" />

      {/* Area de obras (terra) */}
      <rect x="710" y="670" width="160" height="90" rx="6" fill="#b08d57" opacity="0.55" />

      {/* Area restrita (faixa de risco) */}
      <rect x="900" y="670" width="260" height="90" rx="6" fill="#c0281f" opacity="0.12" />
      <line x1="900" y1="670" x2="1160" y2="760" stroke="#c0281f" strokeWidth="3" opacity="0.3" />
      <line x1="1160" y1="670" x2="900" y2="760" stroke="#c0281f" strokeWidth="3" opacity="0.3" />

      {/* Arvores decorativas ao longo das vias */}
      {[[60,270],[260,270],[660,270],[990,270],[60,630],[260,630],[660,630],[990,630],[60,850],[1150,850],[440,850],[880,850]].map(([x,y], i) => (
        <circle key={i} cx={x} cy={y} r="9" fill="#3e7a4a" opacity="0.55" />
      ))}
    </svg>
  );
}
