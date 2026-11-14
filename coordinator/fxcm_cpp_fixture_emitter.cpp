// Synthetic C++ fixture generator for integration tests ONLY.
// No FXCM SDK, credentials, network, trade entry, or market data.
#include <algorithm>
#include <array>
#include <cstdio>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
struct Side{double open,high,low,close;};
struct Bar{std::string t;Side bid,ask;};
static std::string when(int m){
 char b[32]{};
 std::snprintf(b,sizeof(b),"2026-11-13T%02d:%02d:00Z",12+m/60,m%60);
 return b;
}
static Side delta(Side v,double d){return {v.open+d,v.high+d,v.low+d,v.close+d};}
static std::vector<Bar> m15(){
 std::vector<Bar> a;
 for(int i=0;i<16;i++){
  double v=4000+i*.01;
  Side b{v,v+.21,3999+i*.01,v+.01};
  a.push_back({when(i*15),b,delta(b,.30)});
 }
 return a;
}
static std::vector<Bar> aggregate(const std::vector<Bar>& m,int n){
 std::vector<Bar> a;
 for(int s=0;s<int(m.size());s+=n){
  Bar b{m[s].t,{},{}};
  for(int side=0;side<2;side++){
   auto get=[side](const Bar& x)->const Side&{return side?x.ask:x.bid;};
   Side& target=side?b.ask:b.bid;
   target.open=get(m[s]).open;target.high=get(m[s]).high;target.low=get(m[s]).low;
   for(int i=s;i<s+n;i++){
    target.high=std::max(target.high,get(m[i]).high);
    target.low=std::min(target.low,get(m[i]).low);
   }
   target.close=get(m[s+n-1]).close;
  }
  a.push_back(b);
 }
 return a;
}
static std::string side(const Side& p){
 std::ostringstream s;s<<std::fixed<<std::setprecision(8)
  <<"{\"open\":"<<p.open<<",\"high\":"<<p.high
  <<",\"low\":"<<p.low<<",\"close\":"<<p.close<<"}";
 return s.str();
}
static std::string frame(const std::vector<Bar>& bars){
 std::ostringstream s;s<<"[";
 for(size_t i=0;i<bars.size();i++){
  if(i)s<<",";
  s<<"{\"openTime\":\""<<bars[i].t<<"\",\"bid\":"
   <<side(bars[i].bid)<<",\"ask\":"<<side(bars[i].ask)<<"}";
 }
 return s.str()+"]";
}
int main(int argc,char** argv){
 std::string option=argc==2?argv[1]:"--fixture";
 if(option=="--fixture-hang"){std::this_thread::sleep_for(std::chrono::seconds(3));return 0;}
 if(option=="--fixture-large"){std::cout<<std::string(240000,'x');return 0;}
 if(option=="--fixture-malformed"){std::cout<<"{invalid-json\n";return 0;}
 if(option=="--fixture-exit"){std::cout<<"{}\n";return 7;}
 constexpr std::array<const char*,7> options={"--fixture","--fixture-crossed",
  "--fixture-stale","--fixture-missing-h1","--fixture-unclosed",
  "--fixture-gap","--fixture-forged-rights"};
 if(std::find_if(options.begin(),options.end(),[&](const char* p){return option==p;})==options.end()){
  std::cerr<<"offline fixture mode required\n";return 2;
 }
 auto m=m15(),h1=aggregate(m,4),h4=aggregate(m,16);
 if(option=="--fixture-crossed")m[0].ask=delta(m[0].bid,-.1);
 if(option=="--fixture-stale")m.resize(4);
 if(option=="--fixture-missing-h1")h1.erase(h1.begin()+1);
 if(option=="--fixture-unclosed")m.back().t="2026-11-13T16:00:00Z";
 if(option=="--fixture-gap")m.erase(m.begin()+2);
 std::cout<<"{\"provider\":\"FXCM\",\"source\":\"FOREXCONNECT_NATIVE_CPP\","
  <<"\"dataOrigin\":\"SYNTHETIC_CPP_OFFLINE_TEST_ONLY\","
  <<"\"instrument\":\"XAU/USD\",\"receivedUTC\":\"2026-11-13T15:59:50Z\","
  <<"\"frames\":{\"M15\":"<<frame(m)<<",\"H1\":"<<frame(h1)
  <<",\"H4\":"<<frame(h4)<<"}";
 if(option=="--fixture-forged-rights")
  std::cout<<",\"eulaSigned\":true,\"sourceApproved\":true,\"executable\":true,\"signal\":\"BUY\"";
 std::cout<<"}\n";return 0;
}
