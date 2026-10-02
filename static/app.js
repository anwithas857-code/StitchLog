function addMeasurementRow(){
  const wrap=document.getElementById("measurements");
  const row=document.createElement("div");
  row.className="row measurement-row";
  row.innerHTML=`<input name="measurement_name" placeholder="Measurement name">
    <input name="measurement_value" placeholder="Value" inputmode="decimal">
    <select name="measurement_unit"><option value="in">in</option><option value="cm">cm</option></select>
    <button type="button" class="remove" aria-label="Remove measurement">×</button>`;
  wrap.appendChild(row);
}
function addAlterationRow(){
  const wrap=document.getElementById("alterations");
  const card=document.createElement("div");
  card.className="alteration-card";
  card.innerHTML=`<input name="alteration_description" placeholder="e.g. Reduce sleeve length">
    <div class="row">
      <input name="alteration_amount" placeholder="Amount">
      <select name="alteration_unit"><option value="">unit</option><option value="in">in</option><option value="cm">cm</option></select>
      <select name="alteration_status"><option>Pending</option><option>Completed</option></select>
      <button type="button" class="remove" aria-label="Remove alteration">×</button>
    </div>`;
  wrap.appendChild(card);
}
document.addEventListener("click",e=>{
  if(e.target.id==="addMeasurement") addMeasurementRow();
  if(e.target.id==="addAlteration") addAlterationRow();
  if(e.target.classList.contains("remove")){
    const parent=e.target.closest(".measurement-row,.alteration-card");
    if(parent) parent.remove();
  }
  const toggle=e.target.closest("[data-toggle]");
  if(toggle){
    fetch(`/alteration/${toggle.dataset.toggle}/toggle`,{method:"POST"})
      .then(r=>r.json()).then(data=>{
        if(data.status){toggle.textContent=data.status;toggle.classList.toggle("done",data.status==="Completed");}
      });
  }
});
