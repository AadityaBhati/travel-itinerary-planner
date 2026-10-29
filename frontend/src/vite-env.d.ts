/// <reference types="vite/client" />

type GoogleMapsApi = {
  maps: {
    Map: new (element: HTMLElement, options: { center: { lat: number; lng: number }; zoom: number; mapTypeId: string }) => {
      fitBounds: (bounds: unknown) => void;
    };
    Marker: new (options: { map: unknown; position: { lat: number; lng: number }; label: string; title: string }) => {
      addListener: (event: string, handler: () => void) => void;
    };
    Polyline: new (options: { map: unknown; path: { lat: number; lng: number }[]; strokeColor: string; strokeWeight: number }) => unknown;
    LatLngBounds: new () => { extend: (position: { lat: number; lng: number }) => void };
  };
};
