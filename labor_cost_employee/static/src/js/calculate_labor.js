odoo.define('labor_cost_employee.calculate_labor',function(require){
    "use strict";
    
var ListController = require('web.ListController');
var ajax = require('web.ajax');

ListController.include({
   renderButtons: function($node) {
	   this._super.apply(this, arguments);
       if (this.$buttons) {
           this.$buttons.find('.o_list_button_labor').click(this.proxy('action_labor'));
           this.$buttons.find('.o_list_button_add').css('display','none');
       }
	},
    action_labor: function(){
	    var self=this;
	    ajax.jsonRpc('/get_action_labor','call',{
		}).then(function(data){
        	return self.do_action(data);
        });
       }
   });
});