import React from 'react';

export const ProfileCard = () => {
  return (
    <>
      <style>
        {`
          .hover-scale {
            transition: transform 700ms ease-out;
          }
          
          .hover-scale:hover {
            transform: scale(1.02);
          }
          
          .image-scale {
            transition: transform 700ms ease-out;
          }
          
          .image-container:hover .image-scale {
            transform: scale(1.03);
          }
          
          .hover-translate {
            transition: transform 500ms ease-out;
          }
          
          .hover-translate:hover {
            transform: translateX(4px);
          }
          
          .hover-scale-sm {
            transition: transform 500ms ease-out;
          }
          
          .hover-scale-sm:hover {
            transform: scale(1.1);
          }
        `}
      </style>
      
      <div className="w-full bg-black flex items-center justify-center py-8">
        <div className="w-full max-w-xs">
          <div className="bg-black rounded-xl shadow-lg shadow-black/80 overflow-hidden hover-scale border border-white/10">
            <div className="relative overflow-hidden image-container">
              <img 
                src="/Cadence.jpeg"
                alt="Cadence Apeiron" 
                className="w-full aspect-square object-cover image-scale"
              />
              <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-black/30 to-transparent pointer-events-none"></div>
            </div>
            
            <div className="p-1.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full overflow-hidden hover-scale-sm ring-2 ring-zinc-700">
                  <img 
                    src="/Cadence.jpeg"
                    alt="Avatar" 
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="hover-translate">
                  <div className="text-sm text-zinc-200">Cadence Apeiron</div>
                  <div className="text-xs text-zinc-500">@cdgtlmda</div>
                </div>
              </div>
              <button 
                onClick={() => window.open('https://github.com/cdgtlmda', '_blank')}
                className="bg-zinc-800 text-zinc-100 rounded-lg px-4 py-2 text-sm font-medium
                         transition-all duration-500 ease-out transform hover:scale-105 
                         hover:bg-zinc-700
                         active:scale-95 hover:shadow-md hover:shadow-black/50"
              >
                Follow
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ProfileCard; 