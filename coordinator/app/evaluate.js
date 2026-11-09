const {processSnapshot}=require('./paper-core');
let input='';process.stdin.on('data',x=>input+=x);process.stdin.on('end',()=>{
 const request=JSON.parse(input),state=request.state;
 const events=processSnapshot(request.raw,request.now,state);
 process.stdout.write(JSON.stringify({state,events}));
});
