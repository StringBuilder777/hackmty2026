'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import type { ComponentType } from 'react';
import type { Stop, Point, Route, BranchId } from '@/lib/types';

// Tipamos dinámicamente el componente para que reconozca todas sus props
interface ShoppingMapProps {
  stops: Stop[];
  origin: Point;
  route: Route | null;
  online: boolean;
  active: BranchId | null;
  picking: boolean;
  onOrigin: (point: Point) => void;
  onFocus: (id: BranchId) => void;
}

const ShoppingMap = dynamic<ShoppingMapProps>(
  () => import('@/components/ShoppingMap') as Promise<{ default: ComponentType<ShoppingMapProps> }>,
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full min-h-[400px] bg-slate-100 animate-pulse flex items-center justify-center text-slate-500 font-medium rounded-lg">
        Cargando mapa...
      </div>
    ),
  }
);

export default function HomePage() {
  const [origin, setOrigin] = useState<Point>({ lat: 25.6866, lng: -100.3161 });
  const [activeBranch, setActiveBranch] = useState<BranchId | null>(null);
  const [isPicking, setIsPicking] = useState<boolean>(false);
  const [route, setRoute] = useState<Route | null>(null);

  // Solución al error de BranchId: hacemos cast con "as BranchId"
  const [stops, setStops] = useState<Stop[]>([
    {
      id: 'branch-1' as BranchId,
      name: 'Sucursal Centro',
      lat: 25.67,
      lng: -100.31,
      products: ['Producto A'],
    },
    {
      id: 'branch-2' as BranchId,
      name: 'Sucursal Poniente',
      lat: 25.69,
      lng: -100.35,
      products: ['Producto B'],
    },
  ]);

  return (
    <main className="flex flex-col md:flex-row h-screen w-full overflow-hidden">
      <div className="w-full md:w-1/3 p-4 bg-white border-r border-slate-200 z-10 overflow-y-auto">
        <h1 className="text-xl font-bold text-slate-800 mb-4">Buenpaso</h1>

        <button
          onClick={() => setIsPicking(!isPicking)}
          className={`px-4 py-2 rounded-md w-full mb-4 text-white font-semibold transition-colors ${
            isPicking ? 'bg-amber-600' : 'bg-emerald-600 hover:bg-emerald-700'
          }`}
        >
          {isPicking ? 'Haz clic en el mapa para fijar origen' : 'Cambiar punto de origen'}
        </button>

        <div className="space-y-2">
          {stops.map((stop) => (
            <div
              key={stop.id}
              onClick={() => setActiveBranch(stop.id)}
              className={`p-3 border rounded-md cursor-pointer ${
                activeBranch === stop.id ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200'
              }`}
            >
              <p className="font-bold text-sm text-slate-800">{stop.name}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="w-full md:w-2/3 h-full relative">
        <ShoppingMap
          stops={stops}
          origin={origin}
          route={route}
          online={true}
          active={activeBranch}
          picking={isPicking}
          onOrigin={(newOrigin: Point) => {
            setOrigin(newOrigin);
            setIsPicking(false);
          }}
          onFocus={(id: BranchId) => setActiveBranch(id)}
        />
      </div>
    </main>
  );
}