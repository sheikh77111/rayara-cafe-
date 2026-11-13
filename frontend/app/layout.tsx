import './globals.css';
import type { Metadata } from 'next';
export const metadata:Metadata={title:'Rayara Café | Play & Dine',description:'Explore the Rayara menu, play games and win rewards for your next visit.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
