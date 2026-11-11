// Gold Precision Pro: read-only MT5 bar exporter.
// Reads the attached broker symbol's CLOSED M15 rates and writes a local CSV
// snapshot in the MT5 Common\Files sandbox. No network and no trading APIs.
#property strict
#property version   "1.00"
#property description "Exports closed XAU M15 rates for local research only; never places orders."

input string InpConfirmedGoldSymbol = ""; // Must exactly match chart symbol, including broker suffix.
input int    InpBarsToExport = 2000;      // Closed M15 bars only.
input int    InpTimerSeconds = 15;
input string InpOutputFile = "GoldPrecision/xauusd-m15.csv";

datetime g_lastClosedBar = 0;

string IsoServer(datetime value)
{
   string out = TimeToString(value, TIME_DATE|TIME_MINUTES);
   StringReplace(out, ".", "-");
   StringReplace(out, " ", "T");
   return out;
}

string IsoUtc(datetime value)
{
   return IsoServer(value) + ":00Z";
}

int ServerUtcOffsetMinutes()
{
   return (int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 60.0);
}

bool ExportClosedM15()
{
   if(InpConfirmedGoldSymbol == "" || _Symbol != InpConfirmedGoldSymbol)
   {
      Print("GoldPrecision export stopped: set InpConfirmedGoldSymbol to the exact chart symbol.");
      return false;
   }
   if(InpBarsToExport < 100 || InpBarsToExport > 10000 || InpTimerSeconds < 5)
   {
      Print("GoldPrecision export stopped: invalid bars/timer bounds.");
      return false;
   }
   int offset = ServerUtcOffsetMinutes();
   if(offset < -840 || offset > 840 || offset % 15 != 0)
   {
      Print("GoldPrecision export stopped: terminal/server UTC offset is unavailable or invalid.");
      return false;
   }

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int copied = CopyRates(InpConfirmedGoldSymbol, PERIOD_M15, 1, InpBarsToExport, rates);
   if(copied < 100)
   {
      PrintFormat("GoldPrecision export waiting for M15 history: copied=%d", copied);
      return false;
   }
   datetime newest = rates[copied - 1].time;
   if(newest == g_lastClosedBar)
      return true;

   int file = FileOpen(InpOutputFile, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',', CP_UTF8);
   if(file == INVALID_HANDLE)
   {
      PrintFormat("GoldPrecision export file error=%d", GetLastError());
      return false;
   }
   FileWrite(file, "symbol", "timeframe", "bar_open_server", "server_utc_offset_minutes",
             "observed_utc", "open", "high", "low", "close", "tick_volume", "real_volume", "spread_points");
   string observed = IsoUtc(TimeGMT());
   for(int i=0; i<copied; i++)
   {
      // CopyRates(start_pos=1) excludes the forming candle. MT5 volume is
      // preserved as tick_volume; it is not described as exchange volume.
      FileWrite(file, InpConfirmedGoldSymbol, "M15", IsoServer(rates[i].time), offset, observed,
                DoubleToString(rates[i].open, _Digits), DoubleToString(rates[i].high, _Digits),
                DoubleToString(rates[i].low, _Digits), DoubleToString(rates[i].close, _Digits),
                (long)rates[i].tick_volume, (long)rates[i].real_volume, (int)rates[i].spread);
   }
   FileFlush(file);
   FileClose(file);
   g_lastClosedBar = newest;
   PrintFormat("GoldPrecision local snapshot exported: symbol=%s M15 rows=%d offset_min=%d closed_bar=%s",
               InpConfirmedGoldSymbol, copied, offset, IsoServer(newest));
   return true;
}

int OnInit()
{
   if(InpTimerSeconds < 5 || InpTimerSeconds > 300)
      return INIT_PARAMETERS_INCORRECT;
   EventSetTimer(InpTimerSeconds);
   ExportClosedM15();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   ExportClosedM15();
}
