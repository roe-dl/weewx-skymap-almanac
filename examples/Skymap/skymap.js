// switch on and off elements of the image
function set_display_in_svg(id,x)
  {
    console.log(id,x)
    let el = document.getElementById(id);
    if (el)
      {
        if (x.target.checked)
          {
            // switch on
            el.style.removeProperty("display");
          }
        else
          {
            // switch off
            el.style.display = "none";
          }
      }
  }
